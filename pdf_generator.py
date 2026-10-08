import io
from datetime import date
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_pdf_statement(user, transactions, totals, piggy_balance, health, cockpit, bill_splits):
    """
    Generates a formal, bank-grade PDF statement for SpendWise.
    All dates strictly formatted as DD-MM-YYYY.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1e1b4b')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6
    )
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#ffffff')
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1e293b')
    )
    table_cell_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=2,
        textColor=colors.HexColor('#1e293b')
    )

    today_dmy = date.today().strftime("%d-%m-%Y")
    story = []

    # 1. Header Row (Brand on Left, Metadata on Right)
    header_data = [
        [
            Paragraph("<b>SPENDWISE</b>", title_style),
            Paragraph(f"<b>Statement Date:</b> {today_dmy}<br/><b>Statement ID:</b> #SW-{today_dmy.replace('-', '')}", subtitle_style)
        ],
        [
            Paragraph("Official Student Financial Statement & Audit Ledger", subtitle_style),
            Paragraph("Currency: <b>INR (Rs.)</b>", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.8 * inch, 3.4 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5"), spaceAfter=14))

    # 2. Account Profile Grid
    account_info = [
        [
            Paragraph("<b>Student Name:</b>", body_text),
            Paragraph(str(user.get("name", "Student")), body_bold),
            Paragraph("<b>Institution:</b>", body_text),
            Paragraph(str(user.get("college_name", "Engineering College")), body_bold),
        ],
        [
            Paragraph("<b>Monthly Stipend/Income:</b>", body_text),
            Paragraph(f"Rs. {float(user.get('monthly_income', 0)):,.2f}", body_bold),
            Paragraph("<b>Runway Remaining:</b>", body_text),
            Paragraph(f"{cockpit.get('runway_days', 0)} Days", body_bold),
        ],
        [
            Paragraph("<b>Daily Safe Spend:</b>", body_text),
            Paragraph(f"Rs. {float(cockpit.get('safe_daily_spend', 0)):,.2f}/day", body_bold),
            Paragraph("<b>Health Score:</b>", body_text),
            Paragraph(f"{health.get('score', 0)}/100 (Grade {health.get('grade', 'N/A')})", body_bold),
        ]
    ]
    info_table = Table(account_info, colWidths=[1.8 * inch, 1.8 * inch, 1.6 * inch, 2.0 * inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # 3. Financial KPI Summary Matrix
    base_inc = float(user.get("monthly_income", 0))
    added_inc = float(totals.get("added_income", 0) or 0)
    total_inc = base_inc + added_inc
    exp = float(totals.get("expenses", 0) or 0)
    bal = total_inc - exp
    piggy = float(piggy_balance or 0)

    summary_data = [
        [
            Paragraph("<b>Total Monthly Inflow</b>", table_header),
            Paragraph("<b>Total Monthly Outflow</b>", table_header),
            Paragraph("<b>Net Runway Balance</b>", table_header),
            Paragraph("<b>Piggy Vault Balance</b>", table_header)
        ],
        [
            Paragraph(f"Rs. {total_inc:,.2f}", body_bold),
            Paragraph(f"Rs. {exp:,.2f}", body_bold),
            Paragraph(f"Rs. {bal:,.2f}", body_bold),
            Paragraph(f"Rs. {piggy:,.2f}", body_bold)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#ffffff")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # 4. Transaction Activity Ledger
    story.append(Paragraph("<b>Recent Transaction Activity Ledger (DD-MM-YYYY)</b>", section_title))
    
    tx_rows = [
        [
            Paragraph("<b>Date (DD-MM-YYYY)</b>", table_header),
            Paragraph("<b>Type</b>", table_header),
            Paragraph("<b>Category</b>", table_header),
            Paragraph("<b>Description</b>", table_header),
            Paragraph("<b>Amount (INR)</b>", table_header),
        ]
    ]
    for idx, tx in enumerate(transactions[:18]):
        amt = float(tx.get("amount", 0))
        ttype = str(tx.get("transaction_type", "expense")).capitalize()
        cat = str(tx.get("category", "General"))
        desc = str(tx.get("description", ""))[:32]
        tdate = str(tx.get("formatted_date", tx.get("transaction_date", "")))
        
        amt_str = f"+Rs. {amt:,.2f}" if ttype.lower() == "income" else f"-Rs. {amt:,.2f}"
        
        tx_rows.append([
            Paragraph(tdate, table_cell),
            Paragraph(ttype, table_cell),
            Paragraph(cat, table_cell),
            Paragraph(desc, table_cell),
            Paragraph(amt_str, table_cell_right)
        ])

    tx_table = Table(tx_rows, colWidths=[1.4 * inch, 0.9 * inch, 1.2 * inch, 2.5 * inch, 1.2 * inch])
    
    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#312e81")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    # Alternating row coloring
    for r in range(1, len(tx_rows)):
        if r % 2 == 0:
            table_styles.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor("#f8fafc")))
            
    tx_table.setStyle(TableStyle(table_styles))
    story.append(tx_table)
    story.append(Spacer(1, 14))

    # 5. Bill Splits Reconciliation (if any)
    if bill_splits:
        story.append(Paragraph("<b>Active Campus Bill Splits</b>", section_title))
        split_rows = [
            [
                Paragraph("<b>Date (DD-MM-YYYY)</b>", table_header),
                Paragraph("<b>Bill Title</b>", table_header),
                Paragraph("<b>Total (INR)</b>", table_header),
                Paragraph("<b>Your Share</b>", table_header),
                Paragraph("<b>Status</b>", table_header),
            ]
        ]
        for s in bill_splits[:5]:
            s_date = str(s.get("formatted_date", s.get("created_date", "")))
            s_title = str(s.get("title", ""))[:28]
            s_tot = f"Rs. {float(s.get('total_amount', 0)):,.2f}"
            s_share = f"Rs. {float(s.get('my_share', 0)):,.2f}"
            s_status = "Settled" if s.get("settled") else "Pending"
            split_rows.append([
                Paragraph(s_date, table_cell),
                Paragraph(s_title, table_cell),
                Paragraph(s_tot, table_cell),
                Paragraph(s_share, table_cell),
                Paragraph(s_status, table_cell)
            ])
        split_table = Table(split_rows, colWidths=[1.4 * inch, 2.6 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch])
        split_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(split_table)
        story.append(Spacer(1, 14))

    # 6. Footer Notes & Watermark
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    footer_text = Paragraph(
        "<b>SPENDWISE AI</b> • Official Student Financial Assistant • Generated on " + today_dmy + 
        " • All dates formatted as DD-MM-YYYY • Confidential Student Financial Record",
        subtitle_style
    )
    story.append(footer_text)

    # Build Document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
