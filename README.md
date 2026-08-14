# pretix Czech bank transfer

This plugin adds a Czech domestic bank-transfer payment provider to pretix. It subclasses the built-in
`BankTransfer` provider and uses its pending-payment, imported-transaction, over/underpayment, duplicate and refund
processing. It adds a stable numeric variable symbol and QR Platba (SPD) presentation.

The built-in `pretix.plugins.banktransfer` plugin needs to be installed and enabled. Bank statement files are imported
through its existing event or organizer bank-data import screen.

Default account details can be configured on the organizer's **Czech bank transfer** settings page. Events inherit
the organizer account number, bank code, IBAN, recipient, variable-symbol prefix, payment instructions, and enabled
state, and can override them in their own payment-provider settings.
