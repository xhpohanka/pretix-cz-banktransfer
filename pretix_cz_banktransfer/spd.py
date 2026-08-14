import base64
import io
from decimal import Decimal

import qrcode
import qrcode.image.svg


def normalize_iban(iban):
    return "".join(iban.split()).upper()


def generate_spd(
    iban: str,
    amount: Decimal,
    currency: str,
    variable_symbol: str,
    message: str = "",
) -> str:
    if not variable_symbol.isdigit() or len(variable_symbol) > 10:
        raise ValueError("Variable symbol must contain at most ten digits.")
    amount = Decimal(amount)
    fields = [
        "SPD", "1.0", f"ACC:{normalize_iban(iban)}", f"AM:{amount:.2f}",
        f"CC:{currency.upper()}", f"X-VS:{variable_symbol}",
    ]
    message = " ".join((message or "").replace("*", " ").split())[:60]
    if message:
        fields.append(f"MSG:{message}")
    return "*".join(fields)


def spd_qr_data_uri(payload: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(output)
    return "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode("ascii")
