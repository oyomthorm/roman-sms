import pytest
from app.services import billing as billing_svc
from app.services import invoice_pdf


def test_render_invoice_returns_pdf_bytes(app, db, associate_org, plan):
    inv, _ = billing_svc.create_invoice(associate_org, plan)
    pdf = invoice_pdf.render_invoice(inv)

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b'%PDF-')
    assert pdf.rstrip().endswith(b'%%EOF')
    # Not a stub — a real invoice is more than a few hundred bytes
    assert len(pdf) > 800


def test_render_invoice_for_paid(app, db, associate_org, plan):
    inv, _ = billing_svc.create_invoice(associate_org, plan)
    billing_svc.mark_paid(
        inv, actor_id=None,
        payment_method='momo',
        payment_reference='MTN-TEST-123',
    )
    pdf = invoice_pdf.render_invoice(inv)
    assert pdf.startswith(b'%PDF-')


def test_render_invoice_for_cancelled(app, db, associate_org, plan):
    inv, _ = billing_svc.create_invoice(associate_org, plan)
    billing_svc.cancel_invoice(inv, actor_id=None, reason='test cancel')
    pdf = invoice_pdf.render_invoice(inv)
    assert pdf.startswith(b'%PDF-')


def test_render_invoice_uses_company_config(app, db, associate_org, plan):
    """Company name should appear in the PDF metadata title author."""
    app.config['COMPANY_NAME'] = 'Test Company Ltd'
    inv, _ = billing_svc.create_invoice(associate_org, plan)
    pdf = invoice_pdf.render_invoice(inv)
    # Metadata author is set from the company name; check embedded bytes
    assert b'Test Company Ltd' in pdf


def test_render_invoice_with_no_payment_instructions(app, db,
                                                    associate_org, plan):
    """Missing PAYMENT_INSTRUCTIONS should not crash; section is skipped."""
    app.config['PAYMENT_INSTRUCTIONS'] = ''
    inv, _ = billing_svc.create_invoice(associate_org, plan)
    pdf = invoice_pdf.render_invoice(inv)
    assert pdf.startswith(b'%PDF-')