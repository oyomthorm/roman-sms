"""
Invoice PDF generation.

Renders an Invoice (already snapshotted at creation) into a PDF the
associate can download and forward to their accountant.

Everything is drawn from the Invoice row — no live lookups against Plan
or Organization — because the invoice is the source of truth once issued.

Uses ReportLab's platypus API. Pure-Python; no system dependencies beyond
the pip wheel.
"""
from datetime import datetime
from io import BytesIO

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


INK = colors.HexColor('#0f172a')
MUTED = colors.HexColor('#64748b')
HEADER_BG = colors.HexColor('#f1f5f9')
RULE = colors.HexColor('#cbd5e1')


def render_invoice(invoice) -> bytes:
    """Return PDF bytes for an invoice row."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f'Invoice {invoice.number}',
        author=_company_name(),
    )

    styles = _styles()
    story = []

    # Header — company name + details
    story.append(Paragraph(_company_name(), styles['CompanyName']))
    details = _company_details_html()
    if details:
        story.append(Paragraph(details, styles['Small']))
    story.append(Spacer(1, 8 * mm))

    # Title
    story.append(Paragraph('INVOICE', styles['Title']))
    story.append(HRFlowable(width='100%', thickness=0.6, color=RULE))
    story.append(Spacer(1, 5 * mm))

    # Two-column: meta on the left, bill-to on the right
    story.append(_meta_and_billto(invoice))
    story.append(Spacer(1, 8 * mm))

    # Line items
    story.append(_line_items(invoice))
    story.append(Spacer(1, 4 * mm))

    # Total row
    story.append(_total_row(invoice))
    story.append(Spacer(1, 10 * mm))

    # Payment instructions (only when unpaid)
    if invoice.status == 'unpaid':
        instructions = current_app.config.get('PAYMENT_INSTRUCTIONS', '')
        if instructions:
            story.append(Paragraph('Payment instructions',
                                   styles['SectionHeading']))
            story.append(Paragraph(instructions, styles['Body']))
            story.append(Spacer(1, 6 * mm))

    # Notes (if any)
    if invoice.note:
        story.append(Paragraph('Notes', styles['SectionHeading']))
        story.append(Paragraph(invoice.note, styles['Body']))
        story.append(Spacer(1, 6 * mm))

    # Footer
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=RULE))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f'Generated {_date(datetime.utcnow())}. '
        f'This invoice reflects the plan as it stood when issued.',
        styles['Small'],
    ))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

PERPETUAL_DAYS = 36500


def _validity_label(days):
    """Human label for the invoice validity column."""
    if not days or days >= PERPETUAL_DAYS:
        return 'No expiry'
    return f'{days} days'

def _meta_and_billto(invoice):
    """Return a two-column table: invoice meta | bill-to block."""
    meta = [
        ['Invoice no.', invoice.number],
        ['Issued', _date(invoice.issued_at)],
        ['Status', _status_label(invoice.status)],
    ]
    if invoice.paid_at:
        meta.append(['Paid', _date(invoice.paid_at)])
    if invoice.payment_method:
        meta.append(['Method', invoice.payment_method.upper()])
    if invoice.payment_reference:
        meta.append(['Reference', invoice.payment_reference])
    if invoice.cancelled_at:
        meta.append(['Cancelled', _date(invoice.cancelled_at)])

    org = invoice.org
    billto = [
        ['Bill to', ''],
        ['', org.name],
    ]
    if org.contact_email:
        billto.append(['', org.contact_email])
    if org.contact_phone:
        billto.append(['', org.contact_phone])
    if getattr(org, 'district', None):
        billto.append(['', org.district.name])

    meta_table = Table(meta, colWidths=[28 * mm, 55 * mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))

    bill_table = Table(billto, colWidths=[18 * mm, 70 * mm])
    bill_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))

    wrapper = Table([[meta_table, bill_table]], colWidths=[85 * mm, 90 * mm])
    wrapper.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def _line_items(invoice):
    rows = [['Description', 'Credits', 'Validity', 'Amount']]
    rows.append([
        invoice.plan_name or 'Plan',
        f'{invoice.credits:,}',
        _validity_label(invoice.validity_days),
        f'{invoice.currency} {float(invoice.amount):,.0f}',
    ])
    t = Table(rows, colWidths=[85 * mm, 30 * mm, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, RULE),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, RULE),
    ]))
    return t


def _total_row(invoice):
    t = Table(
        [['', 'Total', f'{invoice.currency} {float(invoice.amount):,.0f}']],
        colWidths=[130 * mm, 20 * mm, 25 * mm],
    )
    t.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    return {
        'CompanyName': ParagraphStyle(
            'CompanyName', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=15, leading=18,
            textColor=INK,
        ),
        'Title': ParagraphStyle(
            'Title', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=22, leading=26,
            textColor=INK,
        ),
        'SectionHeading': ParagraphStyle(
            'SectionHeading', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=10, leading=13,
            textColor=INK, spaceAfter=4,
        ),
        'Body': ParagraphStyle(
            'Body', parent=base['Normal'],
            fontName='Helvetica', fontSize=10, leading=14,
            textColor=INK,
        ),
        'Small': ParagraphStyle(
            'Small', parent=base['Normal'],
            fontName='Helvetica', fontSize=8, leading=11,
            textColor=MUTED,
        ),
    }


def _company_name():
    return current_app.config.get('COMPANY_NAME', 'Roman SMS')


def _company_details_html():
    parts = []
    for key, prefix in (
        ('COMPANY_ADDRESS', ''),
        ('COMPANY_PHONE', 'Tel: '),
        ('COMPANY_EMAIL', 'Email: '),
        ('COMPANY_TIN', 'TIN: '),
    ):
        val = current_app.config.get(key, '')
        if val:
            parts.append(f'{prefix}{val}')
    return '<br/>'.join(parts)


def _date(dt):
    if not dt:
        return ''
    return dt.strftime('%d %b %Y')


def _status_label(status):
    return {
        'unpaid': 'Unpaid',
        'paid': 'Paid',
        'cancelled': 'Cancelled',
    }.get(status, (status or '').title())