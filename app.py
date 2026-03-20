import os
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import text
from twilio.twiml.messaging_response import MessagingResponse
from werkzeug.utils import secure_filename

from models import Reserva, User, db
from services import notify_status_update, send_whatsapp_message

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///sovereign_media.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

OWNER_WHATSAPP_TO = os.getenv("OWNER_WHATSAPP_TO", "+5531982631228")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def _ensure_admin_user() -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    existing = User.query.filter_by(username=admin_username).first()
    if existing:
        return

    admin = User(username=admin_username)
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()


def _seed_sample_reservas() -> None:
    if Reserva.query.count() > 0:
        return

    amostra: list[Reserva] = [
        Reserva(
            nome="Helena Duarte",
            telefone="whatsapp:+5531991112222",
            cpf="123.456.789-00",
            valor_total=Decimal("4200.00"),
            valor_entrada=Decimal("1200.00"),
            plataforma="Direto",
            checkin=date.fromisoformat("2026-04-02"),
            checkout=date.fromisoformat("2026-04-07"),
            quarto="Suite Imperial",
            status="pendente",
        ),
        Reserva(
            nome="Rafael Costa",
            telefone="whatsapp:+5531988887777",
            cpf="987.654.321-00",
            valor_total=Decimal("3600.00"),
            valor_entrada=Decimal("1800.00"),
            plataforma="Booking",
            checkin=date.fromisoformat("2026-04-10"),
            checkout=date.fromisoformat("2026-04-14"),
            quarto="Suite Safira",
            status="entrada_paga",
        ),
    ]

    db.session.add_all(amostra)
    db.session.commit()


def _migrate_reservas_schema() -> None:
    # Lightweight migration for existing SQLite files without Alembic.
    with db.engine.begin() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(reservas)"))
        }
        if "observacoes" not in columns:
            conn.execute(text("ALTER TABLE reservas ADD COLUMN observacoes TEXT NOT NULL DEFAULT ''"))
        if "comprovante_nome_arquivo" not in columns:
            conn.execute(
                text("ALTER TABLE reservas ADD COLUMN comprovante_nome_arquivo VARCHAR(255) NOT NULL DEFAULT ''")
            )
        if "comprovante_url_publica" not in columns:
            conn.execute(
                text("ALTER TABLE reservas ADD COLUMN comprovante_url_publica TEXT NOT NULL DEFAULT ''")
            )
        if "created_at" not in columns:
            conn.execute(
                text("ALTER TABLE reservas ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            )


with app.app_context():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.create_all()
    _migrate_reservas_schema()
    _ensure_admin_user()
    _seed_sample_reservas()


def _normalize_whatsapp(number: str) -> str:
    cleaned = number.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith("whatsapp:"):
        return cleaned
    return f"whatsapp:{cleaned}"


def _receipt_public_url(filename: str) -> str:
    relative = url_for("uploaded_file", filename=filename, _external=False)
    if PUBLIC_BASE_URL:
        return urljoin(f"{PUBLIC_BASE_URL}/", relative.lstrip("/"))
    return url_for("uploaded_file", filename=filename, _external=True)


def _month_bounds(month_text: str) -> tuple[date, date]:
    year_str, month_str = month_text.split("-", maxsplit=1)
    year = int(year_str)
    month = int(month_str)
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


@app.route("/")
def home() -> Any:
    return render_template("form.html")


@app.route("/reservas", methods=["POST"])
def create_reservation() -> Any:
    guest_name = request.form.get("guest_name", "").strip()
    cpf = request.form.get("cpf", "").strip()
    guest_phone = _normalize_whatsapp(request.form.get("guest_phone", "").strip())
    entry_amount_text = request.form.get("entry_amount", "").strip()
    room = request.form.get("room", "").strip()
    checkin_text = request.form.get("checkin_date", "").strip()
    checkout_text = request.form.get("checkout_date", "").strip()
    notes = request.form.get("notes", "").strip()
    receipt = request.files.get("receipt_file")

    if not all([guest_name, cpf, guest_phone, entry_amount_text, room, checkin_text, checkout_text]):
        flash("Preencha todos os campos obrigatorios.", "error")
        return redirect(url_for("home"))

    if receipt is None or receipt.filename == "":
        flash("O comprovante de pagamento e obrigatorio.", "error")
        return redirect(url_for("home"))

    try:
        checkin = date.fromisoformat(checkin_text)
        checkout = date.fromisoformat(checkout_text)
    except ValueError:
        flash("Datas invalidas. Verifique check-in e check-out.", "error")
        return redirect(url_for("home"))

    try:
        entry_amount = Decimal(entry_amount_text.replace(",", "."))
        if entry_amount < 0:
            raise ValueError("negative amount")
    except Exception:
        flash("Valor de entrada invalido.", "error")
        return redirect(url_for("home"))

    extension = Path(secure_filename(receipt.filename)).suffix
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_filename
    receipt.save(stored_path)

    comprovante_url = _receipt_public_url(stored_filename)

    reserva = Reserva(
        nome=guest_name,
        telefone=guest_phone,
        cpf=cpf,
        valor_total=entry_amount,
        valor_entrada=entry_amount,
        plataforma="site_direto",
        checkin=checkin,
        checkout=checkout,
        quarto=room,
        status="pendente",
        observacoes=notes,
        comprovante_nome_arquivo=stored_filename,
        comprovante_url_publica=comprovante_url,
    )
    db.session.add(reserva)
    db.session.commit()

    owner_message = (
        f"Nova reserva recebida de {guest_name}. "
        f"Quarto: {room}. "
        f"Check-in: {checkin.isoformat()} | Check-out: {checkout.isoformat()}. "
        "Segue comprovante de pagamento em anexo."
    )
    owner_to = _normalize_whatsapp(OWNER_WHATSAPP_TO)

    send_sid = send_whatsapp_message(
        message_body=owner_message,
        to_number=owner_to,
        media_url=comprovante_url,
    )
    if not send_sid:
        app.logger.warning(
            "Nao foi possivel enviar comprovante ao proprietario via WhatsApp para %s",
            owner_to,
        )

    return render_template("success.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str) -> Any:
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/uploads/<path:filename>/download")
@login_required
def download_uploaded_file(filename: str) -> Any:
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=True,
        download_name=filename,
    )


@app.route("/webhooks/twilio/whatsapp", methods=["POST"])
@csrf.exempt
def twilio_whatsapp_webhook() -> str:
    incoming_text = request.form.get("Body", "").strip()
    sender = request.form.get("From", "desconhecido")

    response = MessagingResponse()
    message = response.message()

    if incoming_text:
        message.body(
            "Recebemos sua mensagem no WhatsApp da Pousada Sovereign. "
            "Nossa equipe vai responder em instantes."
        )
    else:
        message.body(
            f"Recebemos seu contato ({sender}). "
            "Envie uma mensagem de texto para continuarmos o atendimento."
        )

    return str(response)


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Acesso autorizado.", "success")
            return redirect(url_for("dashboard"))

        flash("Credenciais invalidas.", "error")

    return render_template_string(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Login Sovereign</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="min-h-screen bg-[#0f0202] text-zinc-100 flex items-center justify-center px-4"
              style="font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
            <form method="post" class="w-full max-w-md rounded-3xl border border-[#d4af3733] bg-[rgba(26,5,5,0.6)] p-8 backdrop-blur-xl">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <h1 class="text-3xl font-semibold tracking-wide text-[#d4af37]">Sovereign Login</h1>
                <p class="mt-2 text-sm text-zinc-300">Painel protegido do proprietario.</p>
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, message in messages %}
                        <p class="mt-3 text-sm {{ 'text-emerald-300' if category == 'success' else 'text-rose-300' }}">{{ message }}</p>
                    {% endfor %}
                {% endwith %}
                <label class="mt-6 block text-sm text-zinc-300">Usuario</label>
                <input name="username" required class="mt-2 w-full rounded-xl border border-[#d4af3730] bg-black/25 px-4 py-3 outline-none focus:ring-2 focus:ring-[#d4af37]">
                <label class="mt-4 block text-sm text-zinc-300">Senha</label>
                <input type="password" name="password" required class="mt-2 w-full rounded-xl border border-[#d4af3730] bg-black/25 px-4 py-3 outline-none focus:ring-2 focus:ring-[#d4af37]">
                <button class="mt-6 w-full rounded-xl bg-[#d4af37] py-3 font-semibold text-[#180808] transition duration-300 hover:scale-[1.02]">Entrar</button>
            </form>
        </body>
        </html>
        """
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout() -> Any:
    logout_user()
    flash("Sessao encerrada.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard() -> Any:
    reservas = Reserva.query.order_by(Reserva.created_at.desc()).all()
    pendentes = Reserva.query.filter_by(status="pendente").count()
    confirmados = Reserva.query.filter(Reserva.status.in_(["entrada_paga", "completo"])).count()
    receita_total = db.session.query(db.func.coalesce(db.func.sum(Reserva.valor_total), 0)).scalar() or Decimal("0.00")
    export_month = request.args.get("month", date.today().strftime("%Y-%m"))

    return render_template(
        "dashboard.html",
        reservations=reservas,
        pendentes=pendentes,
        confirmados=confirmados,
        receita_total=Decimal(receita_total),
        export_month=export_month,
    )


@app.route("/dashboard/exportar-excel", methods=["GET"])
@login_required
def exportar_excel_mes() -> Any:
    month_text = request.args.get("month", date.today().strftime("%Y-%m"))

    try:
        start_month, end_month = _month_bounds(month_text)
    except Exception:
        flash("Mes invalido. Use o formato AAAA-MM.", "error")
        return redirect(url_for("dashboard"))

    reservas = (
        Reserva.query
        .filter(Reserva.checkin <= end_month)
        .filter(Reserva.checkout >= start_month)
        .order_by(Reserva.checkin.asc())
        .all()
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"Reservas {month_text}"

    headers = [
        "ID",
        "Nome",
        "Telefone",
        "CPF",
        "Valor Total",
        "Valor Entrada",
        "Valor Restante",
        "Plataforma",
        "Check-in",
        "Check-out",
        "Quarto",
        "Status",
        "Observacoes",
        "Comprovante URL",
        "Criado em",
    ]
    sheet.append(headers)

    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for reserva in reservas:
        sheet.append(
            [
                reserva.id,
                reserva.nome,
                reserva.telefone,
                reserva.cpf,
                float(reserva.valor_total),
                float(reserva.valor_entrada),
                float(reserva.valor_restante),
                reserva.plataforma,
                reserva.checkin.isoformat(),
                reserva.checkout.isoformat(),
                reserva.quarto,
                reserva.status,
                reserva.observacoes,
                reserva.comprovante_url_publica,
                reserva.created_at.isoformat() if reserva.created_at else "",
            ]
        )

    for column in sheet.columns:
        max_length = 0
        col_letter = column[0].column_letter
        for cell in column:
            value = "" if cell.value is None else str(cell.value)
            if len(value) > max_length:
                max_length = len(value)
        sheet.column_dimensions[col_letter].width = min(max_length + 2, 50)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f"reservas_{month_text}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/confirmar-entrada/<int:reserva_id>", methods=["POST"])
@login_required
def confirmar_entrada(reserva_id: int) -> Any:
    reserva = db.session.get(Reserva, reserva_id)
    if reserva is None:
        flash("Reserva nao encontrada.", "error")
        return redirect(url_for("dashboard"))

    reserva.status = "entrada_paga"
    db.session.commit()
    notify_status_update(reserva, "entrada_paga")

    flash("Entrada confirmada e cliente notificado no WhatsApp.", "success")
    return redirect(url_for("dashboard"))


@app.route("/confirmar-total/<int:reserva_id>", methods=["POST"])
@login_required
def confirmar_total(reserva_id: int) -> Any:
    reserva = db.session.get(Reserva, reserva_id)
    if reserva is None:
        flash("Reserva nao encontrada.", "error")
        return redirect(url_for("dashboard"))

    reserva.status = "completo"
    db.session.commit()
    notify_status_update(reserva, "completo")

    flash("Pagamento total confirmado e cliente notificado no WhatsApp.", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
