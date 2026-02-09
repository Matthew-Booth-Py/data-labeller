"""Generate sample insurance PDF documents for the Getting Started tutorial."""

import os
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def get_output_dir() -> Path:
    """Get the output directory for sample PDFs."""
    return Path(__file__).parent


def create_claim_form_auto():
    """Create an auto insurance claim form PDF."""
    output_path = get_output_dir() / "claim_form_auto_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=20,
        alignment=1,
    )
    story.append(Paragraph("BEAZLEY INSURANCE", header_style))
    story.append(Paragraph("Automobile Claim Form", styles["Heading2"]))
    story.append(Spacer(1, 20))

    # Claim info table
    claim_data = [
        ["Claim Number:", "CLM-2024-AUTO-00147"],
        ["Policy Number:", "POL-AUTO-2024-88421"],
        ["Date of Loss:", "January 15, 2024"],
        ["Date Filed:", "January 18, 2024"],
    ]
    claim_table = Table(claim_data, colWidths=[2 * inch, 4 * inch])
    claim_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(claim_table)
    story.append(Spacer(1, 20))

    # Claimant info
    story.append(Paragraph("CLAIMANT INFORMATION", styles["Heading3"]))
    claimant_data = [
        ["Name:", "Robert J. Thompson"],
        ["Address:", "1842 Oak Valley Drive, Austin, TX 78745"],
        ["Phone:", "(512) 555-0147"],
        ["Email:", "rthompson@email.com"],
        ["Driver License:", "TX-DL-88421547"],
    ]
    claimant_table = Table(claimant_data, colWidths=[2 * inch, 4 * inch])
    claimant_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(claimant_table)
    story.append(Spacer(1, 20))

    # Vehicle info
    story.append(Paragraph("VEHICLE INFORMATION", styles["Heading3"]))
    vehicle_data = [
        ["Year/Make/Model:", "2022 Toyota Camry SE"],
        ["VIN:", "4T1BF1FK5CU512847"],
        ["License Plate:", "TX ABC-1234"],
        ["Mileage:", "34,521 miles"],
    ]
    vehicle_table = Table(vehicle_data, colWidths=[2 * inch, 4 * inch])
    vehicle_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(vehicle_table)
    story.append(Spacer(1, 20))

    # Incident description
    story.append(Paragraph("INCIDENT DESCRIPTION", styles["Heading3"]))
    incident_text = """
    On January 15, 2024, at approximately 3:45 PM, I was traveling southbound on 
    Interstate 35 near exit 234 when the vehicle in front of me suddenly braked. 
    Despite my attempt to stop, my vehicle rear-ended the other car. The collision 
    resulted in damage to my front bumper, hood, and headlights. No injuries were 
    reported. Police report #APD-2024-01547 was filed at the scene.
    """
    story.append(Paragraph(incident_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # Damage estimate
    story.append(Paragraph("DAMAGE ESTIMATE", styles["Heading3"]))
    damage_data = [
        ["Item", "Description", "Estimated Cost"],
        ["Front Bumper", "Replace - cracked and dented", "$1,450.00"],
        ["Hood", "Repair - minor denting", "$650.00"],
        ["Headlight Assembly (L)", "Replace - broken", "$890.00"],
        ["Labor", "Estimated 8 hours", "$960.00"],
        ["", "TOTAL ESTIMATE:", "$3,950.00"],
    ]
    damage_table = Table(damage_data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch])
    damage_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (1, -1), (2, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(damage_table)

    doc.build(story)
    print(f"Created: {output_path}")


def create_claim_form_property():
    """Create a property insurance claim form PDF."""
    output_path = get_output_dir() / "claim_form_property_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=20,
        alignment=1,
    )
    story.append(Paragraph("BEAZLEY INSURANCE", header_style))
    story.append(Paragraph("Property Damage Claim Form", styles["Heading2"]))
    story.append(Spacer(1, 20))

    # Claim info
    claim_data = [
        ["Claim Number:", "CLM-2024-PROP-00289"],
        ["Policy Number:", "POL-HOME-2024-55123"],
        ["Date of Loss:", "February 3, 2024"],
        ["Date Filed:", "February 5, 2024"],
        ["Type of Loss:", "Water Damage - Burst Pipe"],
    ]
    claim_table = Table(claim_data, colWidths=[2 * inch, 4 * inch])
    claim_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(claim_table)
    story.append(Spacer(1, 20))

    # Property owner info
    story.append(Paragraph("PROPERTY OWNER INFORMATION", styles["Heading3"]))
    owner_data = [
        ["Name:", "Sarah M. Williams"],
        ["Property Address:", "4521 Riverside Boulevard, Unit 302, Chicago, IL 60614"],
        ["Mailing Address:", "Same as property address"],
        ["Phone:", "(312) 555-0892"],
        ["Email:", "swilliams@email.com"],
    ]
    owner_table = Table(owner_data, colWidths=[2 * inch, 4 * inch])
    owner_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(owner_table)
    story.append(Spacer(1, 20))

    # Incident description
    story.append(Paragraph("INCIDENT DESCRIPTION", styles["Heading3"]))
    incident_text = """
    On February 3, 2024, during an extreme cold snap with temperatures reaching -15°F, 
    a water pipe in the north-facing wall of the master bathroom burst. The pipe failure 
    occurred while I was at work, and water leaked for approximately 4 hours before I 
    discovered the damage upon returning home at 6:30 PM. The water affected the master 
    bathroom, adjacent bedroom, and the ceiling of the unit below (303). Emergency 
    plumbers from ABC Plumbing (invoice attached) repaired the pipe.
    """
    story.append(Paragraph(incident_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # Damage assessment
    story.append(Paragraph("DAMAGE ASSESSMENT", styles["Heading3"]))
    damage_data = [
        ["Area/Item", "Damage Description", "Est. Replacement Cost"],
        ["Master Bathroom", "Flooring, drywall, vanity cabinet", "$8,500.00"],
        ["Master Bedroom", "Carpet, baseboards, lower drywall", "$4,200.00"],
        ["Hallway", "Carpet water damage", "$1,800.00"],
        ["Personal Property", "Damaged clothing, electronics", "$2,100.00"],
        ["Emergency Repairs", "Plumber emergency call", "$450.00"],
        ["Unit 303 (liability)", "Ceiling damage - pending estimate", "TBD"],
        ["", "TOTAL (excl. Unit 303):", "$17,050.00"],
    ]
    damage_table = Table(damage_data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch])
    damage_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (1, -1), (2, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(damage_table)

    doc.build(story)
    print(f"Created: {output_path}")


def create_policy_homeowners():
    """Create a homeowners policy document PDF."""
    output_path = get_output_dir() / "policy_homeowners_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=10,
        alignment=1,
    )
    story.append(Paragraph("BEAZLEY INSURANCE COMPANY", header_style))
    story.append(Paragraph("Homeowners Insurance Policy", styles["Heading2"]))
    story.append(Paragraph("Policy Declarations Page", styles["Heading3"]))
    story.append(Spacer(1, 20))

    # Policy info
    policy_data = [
        ["Policy Number:", "POL-HOME-2024-77894"],
        ["Policy Period:", "March 1, 2024 to March 1, 2025"],
        ["Policy Type:", "HO-3 Special Form"],
    ]
    policy_table = Table(policy_data, colWidths=[2 * inch, 4 * inch])
    policy_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(policy_table)
    story.append(Spacer(1, 15))

    # Insured info
    story.append(Paragraph("NAMED INSURED", styles["Heading3"]))
    insured_data = [
        ["Primary Insured:", "Michael D. Anderson"],
        ["Co-Insured:", "Jennifer L. Anderson"],
        ["Property Address:", "892 Maple Street, Denver, CO 80220"],
        ["Mailing Address:", "Same as property address"],
    ]
    insured_table = Table(insured_data, colWidths=[2 * inch, 4 * inch])
    insured_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(insured_table)
    story.append(Spacer(1, 15))

    # Coverage summary
    story.append(Paragraph("COVERAGE SUMMARY", styles["Heading3"]))
    coverage_data = [
        ["Coverage", "Limit", "Deductible"],
        ["A - Dwelling", "$485,000", "$2,500"],
        ["B - Other Structures", "$48,500 (10%)", "$2,500"],
        ["C - Personal Property", "$363,750 (75%)", "$2,500"],
        ["D - Loss of Use", "$97,000 (20%)", "None"],
        ["E - Personal Liability", "$500,000", "None"],
        ["F - Medical Payments", "$5,000", "None"],
    ]
    coverage_table = Table(coverage_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch])
    coverage_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(coverage_table)
    story.append(Spacer(1, 15))

    # Premium
    story.append(Paragraph("PREMIUM BREAKDOWN", styles["Heading3"]))
    premium_data = [
        ["Coverage Component", "Annual Premium"],
        ["Dwelling Coverage", "$1,245.00"],
        ["Personal Property", "$312.00"],
        ["Liability Coverage", "$186.00"],
        ["Additional Endorsements", "$94.00"],
        ["Policy Fee", "$25.00"],
        ["TOTAL ANNUAL PREMIUM", "$1,862.00"],
    ]
    premium_table = Table(premium_data, colWidths=[3 * inch, 2 * inch])
    premium_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(premium_table)

    doc.build(story)
    print(f"Created: {output_path}")


def create_loss_report_theft():
    """Create a theft loss report PDF."""
    output_path = get_output_dir() / "loss_report_theft_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=20,
        alignment=1,
    )
    story.append(Paragraph("BEAZLEY INSURANCE", header_style))
    story.append(Paragraph("Loss Report - Theft/Burglary", styles["Heading2"]))
    story.append(Spacer(1, 20))

    # Report info
    report_data = [
        ["Report Number:", "LR-2024-THEFT-00056"],
        ["Claim Number:", "CLM-2024-PROP-00412"],
        ["Policy Number:", "POL-HOME-2024-66234"],
        ["Date of Incident:", "March 12, 2024"],
        ["Date Reported:", "March 12, 2024"],
        ["Police Report #:", "SPD-2024-03-12847"],
    ]
    report_table = Table(report_data, colWidths=[2 * inch, 4 * inch])
    report_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(report_table)
    story.append(Spacer(1, 20))

    # Insured info
    story.append(Paragraph("INSURED INFORMATION", styles["Heading3"]))
    insured_data = [
        ["Name:", "David R. Martinez"],
        ["Address:", "2156 Harbor View Lane, Seattle, WA 98101"],
        ["Phone:", "(206) 555-0234"],
    ]
    insured_table = Table(insured_data, colWidths=[2 * inch, 4 * inch])
    insured_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(insured_table)
    story.append(Spacer(1, 20))

    # Incident narrative
    story.append(Paragraph("INCIDENT NARRATIVE", styles["Heading3"]))
    narrative = """
    On March 12, 2024, between the hours of 10:00 AM and 4:30 PM while the insured 
    was at work, unknown persons gained entry to the residence through a rear 
    basement window. The window frame shows signs of forced entry with pry marks.
    
    Upon returning home at approximately 4:45 PM, the insured discovered the break-in 
    and immediately contacted Seattle Police Department. Officers arrived at 5:15 PM 
    and documented the scene. Detective Sarah Johnson (badge #4521) is assigned to 
    the case.
    
    The intruders appeared to target electronics and jewelry. Master bedroom drawers 
    were ransacked and a wall safe was pried open. The basement window and frame 
    will require replacement.
    """
    story.append(Paragraph(narrative, styles["Normal"]))
    story.append(Spacer(1, 20))

    # Witness statement
    story.append(Paragraph("WITNESS INFORMATION", styles["Heading3"]))
    witness_text = """
    Neighbor (Unit 2154): Mrs. Linda Chen reported seeing an unfamiliar white van 
    parked in the alley behind the properties around 1:00 PM. She did not observe 
    anyone entering or exiting the van. Contact: (206) 555-0891.
    """
    story.append(Paragraph(witness_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # Loss valuation
    story.append(Paragraph("LOSS VALUATION", styles["Heading3"]))
    loss_data = [
        ["Item", "Description", "Purchase Date", "Value"],
        ["MacBook Pro 16\"", "M3 Max, 64GB RAM", "Nov 2023", "$4,299.00"],
        ["iPad Pro 12.9\"", "With Magic Keyboard", "Jan 2024", "$1,598.00"],
        ["Sony A7 IV Camera", "With 24-70mm lens", "Aug 2022", "$3,496.00"],
        ["Jewelry - Watch", "Rolex Submariner", "Gift 2019", "$12,500.00"],
        ["Jewelry - Ring", "Diamond engagement ring", "Dec 2018", "$8,200.00"],
        ["Cash", "From wall safe", "N/A", "$850.00"],
        ["Window Repair", "Basement window + frame", "N/A", "$675.00"],
        ["", "", "TOTAL LOSS:", "$31,618.00"],
    ]
    loss_table = Table(loss_data, colWidths=[1.5 * inch, 1.8 * inch, 1 * inch, 1.2 * inch])
    loss_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(loss_table)

    doc.build(story)
    print(f"Created: {output_path}")


def create_vendor_invoice_repairs():
    """Create a repair vendor invoice PDF."""
    output_path = get_output_dir() / "vendor_invoice_repairs_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Vendor header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=5,
    )
    story.append(Paragraph("QUALITY AUTO BODY SHOP", header_style))
    story.append(Paragraph("1455 Industrial Parkway, Austin, TX 78702", styles["Normal"]))
    story.append(Paragraph("Phone: (512) 555-8800 | Fax: (512) 555-8801", styles["Normal"]))
    story.append(Paragraph("License #: TX-AUTO-44521 | Tax ID: 74-3321567", styles["Normal"]))
    story.append(Spacer(1, 20))

    # Invoice header
    story.append(Paragraph("REPAIR INVOICE", styles["Heading2"]))
    story.append(Spacer(1, 10))

    # Invoice details
    invoice_data = [
        ["Invoice Number:", "QAB-2024-00892"],
        ["Invoice Date:", "January 28, 2024"],
        ["Claim Reference:", "CLM-2024-AUTO-00147"],
        ["Work Order:", "WO-2024-1547"],
    ]
    invoice_table = Table(invoice_data, colWidths=[2 * inch, 4 * inch])
    invoice_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(invoice_table)
    story.append(Spacer(1, 15))

    # Customer/Vehicle
    customer_data = [
        ["Customer:", "Robert J. Thompson"],
        ["Vehicle:", "2022 Toyota Camry SE"],
        ["VIN:", "4T1BF1FK5CU512847"],
        ["Mileage In:", "34,521"],
        ["Mileage Out:", "34,528"],
    ]
    customer_table = Table(customer_data, colWidths=[2 * inch, 4 * inch])
    customer_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(customer_table)
    story.append(Spacer(1, 20))

    # Parts
    story.append(Paragraph("PARTS", styles["Heading3"]))
    parts_data = [
        ["Part #", "Description", "Qty", "Unit Price", "Total"],
        ["TOY-52119-06220", "Front Bumper Cover - Painted", "1", "$875.00", "$875.00"],
        ["TOY-81150-06720", "Headlamp Assembly LH", "1", "$642.00", "$642.00"],
        ["TOY-53301-33901", "Hood Panel", "1", "$485.00", "$485.00"],
        ["MIS-PAINT-001", "Paint Materials & Supplies", "1", "$245.00", "$245.00"],
        ["MIS-MISC-001", "Miscellaneous Hardware", "1", "$48.00", "$48.00"],
        ["", "", "", "Parts Subtotal:", "$2,295.00"],
    ]
    parts_table = Table(parts_data, colWidths=[1.3 * inch, 2.2 * inch, 0.5 * inch, 0.9 * inch, 0.9 * inch])
    parts_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (3, -1), (4, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(parts_table)
    story.append(Spacer(1, 15))

    # Labor
    story.append(Paragraph("LABOR", styles["Heading3"]))
    labor_data = [
        ["Operation", "Hours", "Rate", "Total"],
        ["Remove & Replace Front Bumper", "1.5", "$95.00", "$142.50"],
        ["Remove & Replace Hood", "2.0", "$95.00", "$190.00"],
        ["Remove & Replace Headlamp Assy", "0.8", "$95.00", "$76.00"],
        ["Body Repair - Hood Alignment", "1.5", "$95.00", "$142.50"],
        ["Refinish - Prime, Paint, Clear", "4.0", "$95.00", "$380.00"],
        ["Detail & Clean", "0.5", "$95.00", "$47.50"],
        ["", "", "Labor Subtotal:", "$978.50"],
    ]
    labor_table = Table(labor_data, colWidths=[2.5 * inch, 0.8 * inch, 0.9 * inch, 1 * inch])
    labor_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(labor_table)
    story.append(Spacer(1, 20))

    # Totals
    totals_data = [
        ["Parts Total:", "$2,295.00"],
        ["Labor Total:", "$978.50"],
        ["Subtotal:", "$3,273.50"],
        ["Tax (8.25%):", "$270.07"],
        ["TOTAL DUE:", "$3,543.57"],
    ]
    totals_table = Table(totals_data, colWidths=[4 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"Created: {output_path}")


def create_vendor_invoice_medical():
    """Create a medical services invoice PDF."""
    output_path = get_output_dir() / "vendor_invoice_medical_2024.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Provider header
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=5,
    )
    story.append(Paragraph("WESTSIDE MEDICAL CENTER", header_style))
    story.append(Paragraph("Department of Emergency Medicine", styles["Normal"]))
    story.append(Paragraph("7890 Healthcare Boulevard, Austin, TX 78701", styles["Normal"]))
    story.append(Paragraph("NPI: 1234567890 | Tax ID: 74-5567891", styles["Normal"]))
    story.append(Spacer(1, 20))

    # Invoice header
    story.append(Paragraph("MEDICAL SERVICES INVOICE", styles["Heading2"]))
    story.append(Spacer(1, 10))

    # Invoice details
    invoice_data = [
        ["Invoice Number:", "WMC-2024-INV-04521"],
        ["Date of Service:", "January 15, 2024"],
        ["Invoice Date:", "January 22, 2024"],
        ["Claim Reference:", "CLM-2024-AUTO-00147"],
        ["Account Number:", "PT-2024-88421"],
    ]
    invoice_table = Table(invoice_data, colWidths=[2 * inch, 4 * inch])
    invoice_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(invoice_table)
    story.append(Spacer(1, 15))

    # Patient info
    patient_data = [
        ["Patient Name:", "Robert J. Thompson"],
        ["Date of Birth:", "June 14, 1985"],
        ["Address:", "1842 Oak Valley Drive, Austin, TX 78745"],
        ["Insurance:", "Beazley Auto - PIP Coverage"],
        ["Policy Number:", "POL-AUTO-2024-88421"],
    ]
    patient_table = Table(patient_data, colWidths=[2 * inch, 4 * inch])
    patient_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 20))

    # Diagnosis
    story.append(Paragraph("DIAGNOSIS", styles["Heading3"]))
    diag_data = [
        ["ICD-10 Code", "Description"],
        ["S13.4XXA", "Sprain of ligaments of cervical spine, initial encounter"],
        ["S39.012A", "Strain of muscle/tendon of lower back, initial encounter"],
        ["R51.9", "Headache, unspecified"],
    ]
    diag_table = Table(diag_data, colWidths=[1.5 * inch, 4.5 * inch])
    diag_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 15))

    # Services
    story.append(Paragraph("SERVICES RENDERED", styles["Heading3"]))
    services_data = [
        ["CPT Code", "Description", "Qty", "Charge"],
        ["99284", "Emergency Dept Visit - Moderate Severity", "1", "$485.00"],
        ["72050", "X-Ray, Cervical Spine, 2-3 Views", "1", "$245.00"],
        ["72100", "X-Ray, Lumbosacral Spine, 2-3 Views", "1", "$265.00"],
        ["97140", "Manual Therapy Techniques", "1", "$95.00"],
        ["J1885", "Injection, Ketorolac Tromethamine, 15mg", "2", "$48.00"],
        ["99080", "Special Reports/Forms", "1", "$35.00"],
        ["", "", "Subtotal:", "$1,173.00"],
    ]
    services_table = Table(services_data, colWidths=[1 * inch, 3 * inch, 0.5 * inch, 1 * inch])
    services_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(services_table)
    story.append(Spacer(1, 20))

    # Totals
    totals_data = [
        ["Total Charges:", "$1,173.00"],
        ["Insurance Adjustment:", "-$0.00"],
        ["Amount Due from Insurance:", "$1,173.00"],
    ]
    totals_table = Table(totals_data, colWidths=[4 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 20))

    # Provider signature
    story.append(Paragraph("Attending Physician: Dr. Amanda Chen, MD", styles["Normal"]))
    story.append(Paragraph("NPI: 1987654321", styles["Normal"]))

    doc.build(story)
    print(f"Created: {output_path}")


def generate_all_samples():
    """Generate all sample PDF documents."""
    print("Generating sample insurance documents...")
    print("=" * 50)
    
    create_claim_form_auto()
    create_claim_form_property()
    create_policy_homeowners()
    create_loss_report_theft()
    create_vendor_invoice_repairs()
    create_vendor_invoice_medical()
    
    print("=" * 50)
    print("All sample documents generated successfully!")


if __name__ == "__main__":
    generate_all_samples()
