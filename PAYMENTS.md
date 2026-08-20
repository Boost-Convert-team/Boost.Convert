# BoostConvert PRO — Mercado Pago

O BoostConvert PRO é uma assinatura recorrente de R$ 25,90 por mês. A
contratação usa o Card Payment Brick e a API de Assinaturas do Mercado Pago;
não usa a Payments API para iniciar o PRO.

## Fluxo

1. `GET /checkout-pro` carrega MercadoPago.js e o Card Payment Brick.
2. O Brick tokeniza o cartão no navegador e permite somente uma parcela.
3. O frontend envia apenas o CardToken para `POST /api/payments/checkout`.
4. O backend obtém usuário, plano, valor e moeda internamente.
5. `MercadoPagoGateway` chama `sdk.preapproval().create()` com uma chave de
   idempotência persistida.
6. O acesso PRO só é liberado após uma fatura recorrente aprovada ser
   confirmada no Mercado Pago.

O CardToken é transitório. Número do cartão, CVV, CardToken e segredos não são
persistidos nem registrados em logs.

## Webhooks

Configure `https://boostconvert.com.br/webhooks/mercado-pago` no painel do
Mercado Pago para os tópicos `subscription_preapproval` e
`subscription_authorized_payment`.

O endpoint valida `x-signature` com `WebhookSignatureValidator` do SDK oficial.
Após validar, consulta `sdk.preapproval().get()` ou `sdk.invoice().get()` e só
então atualiza assinatura, histórico de cobranças e entitlement PRO.

## Configuração

Variáveis obrigatórias em produção:

```text
MERCADOPAGO_PUBLIC_KEY
MERCADOPAGO_ACCESS_TOKEN
MERCADOPAGO_WEBHOOK_URL
MERCADOPAGO_WEBHOOK_SECRET
```

Instalação e migrações:

```bash
cd /var/www/boostconvert/backend
/var/www/boostconvert/venv/bin/python -m pip install -r requirements.txt
/var/www/boostconvert/venv/bin/python -m flask --app app:create_app db upgrade
sudo systemctl restart boostconvert
sudo systemctl status boostconvert --no-pager -l
sudo journalctl -u boostconvert -f
```
