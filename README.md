# Sovereign Suite - WhatsApp Media Edition

Sistema de reservas da pousada com upload de comprovante, notificacao automatica no WhatsApp do proprietario e exportacao mensal em Excel no dashboard.

## Funcionalidades

- Formulario do hospede com campos obrigatorios: nome, CPF, WhatsApp, valor de entrada, quarto, periodo e comprovante.
- Upload do comprovante e envio automatico para o WhatsApp do proprietario via Twilio (texto + midia).
- Dashboard protegido por login com acoes de confirmacao.
- Exportacao de planilha Excel por mes com todos os hospedes que passaram pela pousada no periodo selecionado.

## Dependencias

Instale tudo com:

```bash
pip install -r requirements.txt
```

Pacotes principais ja incluidos:

- Flask
- Flask-Login
- Flask-WTF
- Flask-SQLAlchemy
- Twilio
- openpyxl
- gunicorn

## Variaveis de ambiente

Crie `.env` baseado em `.env.example` e configure:

- `SECRET_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`
- `OWNER_WHATSAPP_TO`
- `PUBLIC_BASE_URL` (URL publica do deploy ou ngrok)
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## Rodar localmente

```bash
python app.py
```

URLs locais:

- Formulario: `http://127.0.0.1:5000/`
- Login do proprietario: `http://127.0.0.1:5000/login`

## Publicar para acesso 24h (sem depender do PC local)

O projeto ja esta preparado para deploy com:

- `wsgi.py`
- `Procfile`
- `render.yaml`
- `Dockerfile`
- `runtime.txt`

### Opcao recomendada: Render

1. Suba o projeto em um repositorio Git.
2. No Render, crie Blueprint apontando para o repo.
3. O Render vai ler `render.yaml`, criar Web Service + Postgres e publicar.
4. Configure no painel as variaveis secretas (Twilio e senha admin).
5. Atualize `PUBLIC_BASE_URL` para a URL final do Render.
6. No Twilio Sandbox/WhatsApp Sender, use o webhook:

`https://SEU-DOMINIO/webhooks/twilio/whatsapp`

Com isso, o sistema fica online 24h e independente da sua maquina local.

## Observacao sobre midia no WhatsApp

Para o comprovante chegar como midia, o arquivo precisa estar em URL publica valida. Em local, use ngrok. Em producao, use a URL do seu deploy fixo.