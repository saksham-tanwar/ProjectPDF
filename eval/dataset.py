"""Golden questions for the corpus in `corpus.py`.

Each question names the page(s) that actually answer it, by page title so the set cannot drift when pages move.
Most questions are worded differently from the document, so a retriever cannot pass on word overlap alone;
`keyword_friendly` marks the ones that do share wording, which shows where lexical and semantic retrieval each earn
their keep. Several questions have a near-miss page in the same document (accessories cover vs machine cover,
expenses vs working abroad, results vs results by city size) to make ordering, not just recall, matter.
"""
from dataclasses import dataclass

from eval.corpus import page_number


@dataclass(frozen=True)
class Question:
    document: str
    text: str
    page_titles: tuple[str, ...]
    keyword_friendly: bool = False

    @property
    def pages(self) -> set[int]:
        return {page_number(self.document, title) for title in self.page_titles}


QUESTIONS: list[Question] = [
    # --- Northwind manual ---
    Question("northwind-manual", "How long is the machine guaranteed for?", ("Cover and claims",)),
    Question("northwind-manual", "What voids the warranty?", ("Cover and claims",), keyword_friendly=True),
    Question("northwind-manual", "How long are the spare baskets covered for?", ("Accessories",)),
    Question("northwind-manual", "Can I get my money back if I change my mind?", ("Sending items back",)),
    Question("northwind-manual", "Who pays postage when sending a machine back?", ("Sending items back",), keyword_friendly=True),
    Question("northwind-manual", "What happens if a local shop repairs it?", ("Service network",)),
    Question("northwind-manual", "How often should I remove limescale?", ("Cleaning and descaling",)),
    Question("northwind-manual", "Why should I avoid vinegar?", ("Cleaning and descaling",), keyword_friendly=True),
    Question("northwind-manual", "Can I use distilled water?", ("Water",)),
    Question("northwind-manual", "My coffee tastes sour and pours too quickly.", ("Brewing",)),
    Question("northwind-manual", "How much coffee goes in a double basket?", ("Brewing",), keyword_friendly=True),
    Question("northwind-manual", "Why is there no pressure when frothing?", ("Milk",)),
    Question("northwind-manual", "How hot does the water get and how long does it take?", ("Setting up",)),
    Question("northwind-manual", "Is it safe around young children?", ("Safety",)),
    Question("northwind-manual", "Nothing comes out of the group head, what do I do?", ("Troubleshooting",)),
    Question("northwind-manual", "What does a blinking orange light mean?", ("Troubleshooting",)),
    Question("northwind-manual", "How loud is it and how much does it weigh?", ("Specifications",)),
    Question("northwind-manual", "What is in the box?", ("Unpacking",), keyword_friendly=True),
    Question("northwind-manual", "What email address do I use for a claim?", ("Cover and claims",), keyword_friendly=True),
    Question("northwind-manual", "What size tamper fits?", ("Accessories",), keyword_friendly=True),
    Question("northwind-manual", "What is the pump pressure at the basket?", ("Specifications",), keyword_friendly=True),
    # --- Aurora remote policy ---
    Question("aurora-remote-policy", "How long must I work here before working from home?", ("Who is eligible",)),
    Question("aurora-remote-policy", "Which staff cannot work remotely full time?", ("Who is eligible",), keyword_friendly=True),
    Question("aurora-remote-policy", "What if my manager says no?", ("Requesting remote work",)),
    Question("aurora-remote-policy", "Is there money for a desk and chair?", ("Equipment",)),
    Question("aurora-remote-policy", "Do I have to give the money back if I quit?", ("Ending an arrangement",)),
    Question("aurora-remote-policy", "When am I expected to be online?", ("Hours and availability",)),
    Question("aurora-remote-policy", "Can I spend a month working from Spain?", ("Working from abroad",)),
    Question("aurora-remote-policy", "Will the company pay my internet bill?", ("Expenses",)),
    Question("aurora-remote-policy", "Can I claim the cost of a shared office?", ("Expenses",), keyword_friendly=True),
    Question("aurora-remote-policy", "Is my commute to head office claimable?", ("Expenses",), keyword_friendly=True),
    Question("aurora-remote-policy", "What should I do if I think data has leaked?", ("Information security",)),
    Question("aurora-remote-policy", "Can I keep files in my own Dropbox?", ("Information security",)),
    Question("aurora-remote-policy", "Do I need a desk assessment at home?", ("Health and safety",)),
    Question("aurora-remote-policy", "How do I book a seat when I come in?", ("Office space",)),
    Question("aurora-remote-policy", "What is the address for reporting a breach?", ("Information security",), keyword_friendly=True),
    Question("aurora-remote-policy", "How many working days abroad are allowed?", ("Working from abroad",), keyword_friendly=True),
    # --- Lakeside heat study ---
    Question("lakeside-heat-study", "How much cooler are leafy neighbourhoods?", ("Abstract",)),
    Question("lakeside-heat-study", "Why did they leave out cities by the sea?", ("Site selection",)),
    Question("lakeside-heat-study", "How high were the sensors placed?", ("Method",), keyword_friendly=True),
    Question("lakeside-heat-study", "How did they check the instruments were accurate?", ("Calibration",)),
    Question("lakeside-heat-study", "How were broken readings handled?", ("Data quality",)),
    Question("lakeside-heat-study", "How many observations were kept?", ("Data quality",), keyword_friendly=True),
    Question("lakeside-heat-study", "At what time of day does shade help most?", ("Results",)),
    Question("lakeside-heat-study", "Does light-coloured pavement help?", ("Results",), keyword_friendly=True),
    Question("lakeside-heat-study", "Was the effect the same in smaller, sparser towns?", ("Results by city size",)),
    Question("lakeside-heat-study", "Why might these findings not apply in Dubai?", ("Limitations",)),
    Question("lakeside-heat-study", "What do the authors advise city planners to do?", ("Conclusion",)),
    Question("lakeside-heat-study", "Who paid for the research?", ("Funding",), keyword_friendly=True),
    Question("lakeside-heat-study", "What resolution was the aerial imagery?", ("Method",), keyword_friendly=True),
    Question("lakeside-heat-study", "What is working paper 2025-04 called?", ("Front matter",), keyword_friendly=True),
]
