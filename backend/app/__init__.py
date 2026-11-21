"""RastroJuliaca backend."""
import email_validator

# Las cuentas ficticias de demostración y pruebas usan el dominio reservado ".test" (RFC 2606).
if "test" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")
