# pretix Czech bank transfer

This plugin adds a Czech domestic bank-transfer payment provider to pretix. It subclasses the built-in
`BankTransfer` provider and uses its pending-payment, imported-transaction, over/underpayment, duplicate and refund
processing. It adds a stable numeric variable symbol and QR Platba (SPD) presentation.

The built-in `pretix.plugins.banktransfer` plugin needs to be installed and enabled. Bank statement files are imported
through its existing event or organizer bank-data import screen.
