"""A deterministic PDF corpus for evaluation.

Written in code rather than checked in as binaries so every fact, and the page it lives on, is reviewable. Each
document deliberately contains distractor pages that share vocabulary with the questions without answering them —
without those, retrieval looks perfect and the measurement says nothing.

Pages are referenced by title (see `page_number`), so inserting a page never silently invalidates the golden set.
"""
from io import BytesIO
from pathlib import Path

Page = tuple[str, str]  # (title, body)

NORTHWIND: list[Page] = [
    ("Front matter", """Northwind NX-200 Espresso Machine, Owner's Manual.
Model NX-200, first published March 2024, revision C.
Covers installation, daily use, cleaning, cover and service for the NX-200 domestic machine."""),
    ("Contents", """Safety. Unpacking. Water. Setting up. Brewing. Milk. Cleaning and descaling.
Accessories. Cover and claims. Sending items back. Service network. Troubleshooting. Specifications."""),
    ("Safety", """Do not immerse the base in water. The steam wand reaches 145 degrees Celsius and can scald.
Children under 12 must not operate the machine without supervision.
Unplug the machine before removing the drip tray or the water reservoir."""),
    ("Unpacking", """The box contains the machine, a portafilter, two baskets, a plastic tamper and a water hardness strip.
Keep the packaging for thirty days in case the machine has to travel back to us.
Remove the transit foam from inside the reservoir bay before first use."""),
    ("Water", """Use fresh cold water only. Softened water below 50 ppm causes the boiler probe to misread.
Never fill the reservoir with sparkling or distilled water.
The supplied hardness strip tells you which descaling interval on the cleaning page applies to you."""),
    ("Setting up", """Fill the reservoir to the MAX line, which holds 1.8 litres.
The boiler reaches its target temperature of 93 degrees Celsius in about 90 seconds from cold.
Run two blank cycles through the group head before making the first drink of the day."""),
    ("Brewing", """Use 18 grams of ground coffee for a double basket and aim for 36 grams in the cup.
A correct extraction runs between 25 and 30 seconds.
If the shot runs fast and tastes sour, grind finer. If it drips and tastes bitter, grind coarser."""),
    ("Milk", """Purge the steam wand before and after each jug of milk.
Texture milk with the tip just under the surface until the jug is too hot to hold.
Milk residue baked onto the wand is the most common cause of poor steam pressure."""),
    ("Cleaning and descaling", """Backflush the group head with plain water every day and with detergent once a week.
Descale every eight weeks in hard water areas, or every four months in soft water areas.
Use a citric acid solution; vinegar damages the internal seals and voids cover."""),
    ("Accessories", """Bottomless portafilters, a 58 mm tamper and spare baskets are sold separately.
Accessories carry their own six month cover, separate from the cover on the machine itself.
Third-party baskets may not seat correctly and are not supported."""),
    ("Cover and claims", """Northwind covers manufacturing defects for two years from the date of purchase.
Cover does not extend to limescale damage, cosmetic marks or machines opened by unauthorised repairers.
To make a claim, email support@northwind.example with the serial number from the base plate."""),
    ("Sending items back", """Unused machines in their original packaging may be sent back within thirty days for a full refund.
Return postage is paid by the customer unless the machine arrived damaged.
Refunds are issued to the original payment method within fourteen working days of the machine arriving back."""),
    ("Service network", """Authorised service partners are listed at northwind.example/service.
Repairs carried out by anyone else end cover immediately, even within the first two years.
Out-of-cover repairs are quoted before work begins and carry a three month guarantee on the parts replaced."""),
    ("Troubleshooting", """No water reaching the group head usually means the pump has lost its prime: run the steam wand for ten seconds.
A flashing amber light indicates the machine is descaling and cannot brew.
Loud vibration while pumping normally means the reservoir is empty or seated incorrectly."""),
    ("Specifications", """Power 1450 watts. Pump pressure 9 bar at the basket. Boiler capacity 300 millilitres.
Weight 11.2 kilograms. Footprint 24 by 33 centimetres. Cable length 1.2 metres.
Noise while pumping is typically 62 decibels at one metre."""),
]

AURORA: list[Page] = [
    ("Front matter", """Aurora Analytics, Remote Working Policy.
Effective 1 January 2025, replacing the interim policy of June 2023.
Applies to all permanent staff and to contractors engaged for longer than three months."""),
    ("Purpose", """This policy sets out where staff may work, what the company pays for and what it expects in return.
It should be read alongside the Information Security Standard and the Travel and Expenses Policy.
Nothing here changes contractual hours or annual leave."""),
    ("Who is eligible", """Staff may work remotely after completing their first sixty days of employment.
Roles that require access to the secure lab in Building C are excluded from full-time remote work.
Managers may approve a hybrid pattern of up to three days a week away from the office at their discretion."""),
    ("Requesting remote work", """Requests go through the People portal and are answered within ten working days.
A refusal must give a business reason in writing and may be appealed once to the department head.
Approved arrangements are reviewed every six months."""),
    ("Equipment", """Each remote worker receives a one-off allowance of 600 pounds for a desk, chair and monitor.
Laptops remain the property of Aurora Analytics and must be returned when employment ends.
The allowance is claimed through the Finance portal and is paid with the following month's salary."""),
    ("Office space", """Desks at the registered office are booked through the same portal and are not assigned permanently.
Staff working mainly from home should book a desk at least a day ahead when visiting.
Meeting rooms larger than six seats are reserved for cross-team sessions."""),
    ("Hours and availability", """Core hours are 10:00 to 15:00 in the employee's registered time zone.
Outside core hours staff may arrange their working day as they wish, provided weekly hours are met.
Calendars must show working hours accurately so colleagues can book time without asking."""),
    ("Working from abroad", """Working outside your country of employment needs approval from People and Finance because of tax residency.
Approvals are normally limited to twenty working days a year.
Equipment insurance does not cover laptops taken outside the country without prior notice."""),
    ("Expenses", """Home broadband is not reimbursed. Coworking desks are reimbursed up to 200 pounds a month with prior approval.
Travel to the registered office is treated as commuting and is not claimable.
Travel to any other Aurora site is claimable at standard rates."""),
    ("Information security", """Company data must not be stored on personal devices, including personal cloud storage accounts.
Remote workers must use the company VPN when connecting from public networks.
Any suspected breach must be reported to security@aurora.example within one hour of discovery."""),
    ("Health and safety", """Remote workers complete a short workstation self-assessment once a year.
The company pays for an occupational health assessment where the self-assessment flags a risk.
Accidents while working at home are reported the same way as accidents on site."""),
    ("Ending an arrangement", """Either side may end a remote arrangement with four weeks' notice.
The equipment allowance is not repayable if the arrangement ends after six months.
Staff who leave within six months of claiming the allowance repay it pro rata from final salary."""),
]

LAKESIDE: list[Page] = [
    ("Front matter", """Lakeside Institute. Urban Heat and Tree Canopy in Mid-Sized Cities.
Working paper 2025-04. Authors: R. Iyer, M. Okonjo and L. Fernandes."""),
    ("Abstract", """We measured summer air temperature across eleven mid-sized cities and compared readings with tree canopy cover.
Districts with canopy cover above 30 percent were on average 2.4 degrees Celsius cooler at midday than districts below 10 percent."""),
    ("Background", """Earlier work has focused on large metropolitan areas, where district heating and tall buildings dominate the heat balance.
Mid-sized cities have been studied less often, although most urban growth this decade is happening in them.
Previous canopy estimates relied on coarse satellite imagery that misses street trees entirely."""),
    ("Site selection", """Cities were chosen to span a range of population densities between 80,000 and 400,000 residents.
Within each city, districts were sampled to cover the full range of canopy cover available locally.
Coastal cities were excluded because sea breeze dominates afternoon cooling."""),
    ("Method", """Sensors were mounted 2.5 metres above ground on lamp posts, away from walls and parked vehicles.
Readings were taken every five minutes between June and September 2024.
Canopy cover was derived from aerial imagery at 25 centimetre resolution and verified by field survey in a tenth of sites."""),
    ("Calibration", """All sensors were calibrated against a reference thermometer in a water bath before deployment.
Units drifting by more than 0.2 degrees Celsius were rejected before installation.
Calibration was repeated on recovered units at the end of the season."""),
    ("Data quality", """Four sensors failed during the heatwave of late July and were excluded from the analysis.
Readings more than four standard deviations from the district mean were treated as faults and discarded.
The final dataset contains 1.42 million observations from 318 working sensors."""),
    ("Results", """The cooling effect was strongest between 13:00 and 16:00 and almost absent before sunrise.
Streets with continuous canopy on both sides were cooler than streets with the same total canopy split unevenly.
Surface material mattered less than canopy: pale paving reduced midday temperature by only 0.3 degrees Celsius."""),
    ("Results by city size", """The effect held in every city but was about a third weaker in the least dense sites.
Denser districts trap more heat overnight, so daytime shade makes a larger difference there.
No city showed a reversal of the relationship."""),
    ("Limitations", """The study covers a single summer, so year-to-year variation is not captured.
All eleven cities lie in temperate climates, and the findings may not transfer to arid or tropical settings.
Sensor placement on lamp posts may under-represent conditions at pedestrian height in narrow streets."""),
    ("Conclusion", """Planting for continuity along a street produces more cooling than the same number of trees scattered across a district.
We recommend that city planners set a minimum canopy target of 30 percent for residential districts."""),
    ("Funding", """The work was funded by the Lakeside Institute's own research budget.
Two authors previously consulted for a municipal planning department; the funder had no role in the analysis.
Data and analysis code are available on request."""),
]

CORPUS: dict[str, list[Page]] = {
    "northwind-manual": NORTHWIND,
    "aurora-remote-policy": AURORA,
    "lakeside-heat-study": LAKESIDE,
}


def page_number(document: str, title: str) -> int:
    """1-based page number of a titled page. Raises if the title is gone, so the golden set cannot drift silently."""
    titles = [page_title for page_title, _ in CORPUS[document]]
    if title not in titles:
        raise KeyError(f"{document} has no page titled {title!r}. Available: {titles}")
    return titles.index(title) + 1


def build_pdf(pages: list[Page]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for title, body in pages:
        y = 780
        pdf.drawString(60, y, title)
        y -= 28
        for line in body.splitlines():
            for piece in _wrap(line, 90):
                pdf.drawString(60, y, piece)
                y -= 18
            y -= 4
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _wrap(line: str, width: int) -> list[str]:
    rows, current = [], ""
    for word in line.split():
        if len(current) + len(word) + 1 > width:
            rows.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*rows, current] if current else rows or [""]


def write_corpus(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, pages in CORPUS.items():
        path = directory / f"{name}.pdf"
        path.write_bytes(build_pdf(pages))
        paths[name] = path
    return paths
