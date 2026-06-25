from django.test import SimpleTestCase

from catalog.pii import EMAIL_REDACTED, PHONE_REDACTED, PiiSanitizer


class PiiSanitizerTests(SimpleTestCase):
    def test_redacts_email_patterns(self):
        text = "Please contact me at sara.jamali@example.com for updates."
        sanitized = PiiSanitizer.sanitize_text(text)

        self.assertIn(EMAIL_REDACTED, sanitized)
        self.assertNotIn("sara.jamali@example.com", sanitized)

    def test_redacts_iranian_phone_patterns_latin_digits(self):
        text = "Call me at 09121234567 if the tote is available."
        sanitized = PiiSanitizer.sanitize_text(text)

        self.assertIn(PHONE_REDACTED, sanitized)
        self.assertNotIn("09121234567", sanitized)

    def test_redacts_iranian_phone_patterns_persian_digits(self):
        text = "شماره من ۰۹۱۷۱۱۲۲۳۳۴ است."
        sanitized = PiiSanitizer.sanitize_text(text)

        self.assertIn(PHONE_REDACTED, sanitized)
        self.assertNotIn("09171122334", sanitized)
        self.assertNotIn("۰۹۱۷۱۱۲۲۳۳۴", sanitized)

    def test_redacts_international_phone_patterns(self):
        text = "My US number is +1 (415) 555-0199 for delivery questions."
        sanitized = PiiSanitizer.sanitize_text(text)

        self.assertIn(PHONE_REDACTED, sanitized)
        self.assertNotIn("415", sanitized)
        self.assertNotIn("555-0199", sanitized)

    def test_redacts_plus_98_iranian_international_format(self):
        text = "Reach me at +98 912 555 0199 about order PRS-ORD-001."
        sanitized = PiiSanitizer.sanitize_text(text)

        self.assertIn(PHONE_REDACTED, sanitized)
        self.assertNotIn("+98 912 555 0199", sanitized)

    def test_customer_ref_is_opaque(self):
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(
            PiiSanitizer.customer_ref(customer_id),
            f"customer-{customer_id}",
        )
