"""
Identity Generator
==================
Generates realistic fake Indian customer identities for COD orders.
Supports custom address pools from config or auto-generation.
"""

import random
import string
from typing import List, Optional, Set

from bot.config import AutoGenerateConfig, BotConfig, CustomerAddress


# ── Name Pools ────────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ayaan", "Krishna", "Ishaan", "Shaurya", "Atharva", "Advik", "Pranav",
    "Advaith", "Aryan", "Dhruv", "Kabir", "Ritvik", "Aarush", "Kian",
    "Darsh", "Yash", "Harsh", "Rohit", "Amit", "Rahul", "Suresh",
    "Vikram", "Nikhil", "Rohan", "Kunal", "Aakash", "Deepak", "Manish",
    "Rajesh", "Sanjay", "Gaurav", "Ankit", "Varun", "Sachin", "Mohit",
]

FIRST_NAMES_FEMALE = [
    "Aanya", "Diya", "Saanvi", "Myra", "Ananya", "Aadhya", "Aarohi",
    "Priya", "Riya", "Shreya", "Neha", "Pooja", "Divya", "Kavya",
    "Ishita", "Meera", "Nisha", "Tanvi", "Aditi", "Anjali", "Kritika",
    "Megha", "Pallavi", "Simran", "Sonal", "Swati", "Tanya", "Kriti",
    "Nikita", "Sakshi", "Shikha", "Sneha", "Varsha", "Kiara", "Aisha",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Shah",
    "Reddy", "Nair", "Joshi", "Iyer", "Agarwal", "Mehta", "Chopra",
    "Malhotra", "Kapoor", "Chauhan", "Yadav", "Jain", "Mishra",
    "Pandey", "Trivedi", "Deshmukh", "Patil", "Kulkarni", "Thakur",
    "Banerjee", "Mukherjee", "Ghosh", "Das", "Bose", "Sen", "Roy",
    "Pillai", "Menon", "Rao", "Raju", "Shetty", "Hegde", "Naidu",
]

STREET_PREFIXES = [
    "MG Road", "Station Road", "Main Road", "Park Street", "Gandhi Nagar",
    "Nehru Marg", "Rajaji Street", "Tagore Lane", "Subhash Road",
    "Ring Road", "Civil Lines", "Sector", "Phase", "Block",
    "Sadar Bazaar", "Mall Road", "GT Road", "Link Road", "Highway Road",
]

AREA_SUFFIXES = [
    "Colony", "Nagar", "Vihar", "Enclave", "Extension", "Layout",
    "Garden", "Park", "Heights", "Residency", "Complex", "Apartments",
    "Society", "Phase", "Block", "Sector", "Ward", "Mohalla",
]

EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "rediffmail.com", "protonmail.com", "yahoo.in",
]


class IdentityGenerator:
    """Generates realistic fake customer identities."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.customer_pool = config.customers
        self.auto_config = config.auto_generate
        self._used_emails: Set[str] = set()
        self._used_phones: Set[str] = set()

    def generate(self) -> CustomerAddress:
        """
        Generate a customer identity.
        Uses pool if available, otherwise auto-generates.
        """
        if self.customer_pool:
            return random.choice(self.customer_pool)
        return self._auto_generate()

    def _auto_generate(self) -> CustomerAddress:
        """Auto-generate a realistic Indian customer identity."""
        # Pick gender and name
        is_male = random.random() > 0.45
        first_name = random.choice(FIRST_NAMES_MALE if is_male else FIRST_NAMES_FEMALE)
        last_name = random.choice(LAST_NAMES)

        # Generate unique email
        email = self._generate_email(first_name, last_name)

        # Generate unique phone
        phone = self._generate_phone()

        # Pick province and city
        province = random.choice(self.auto_config.provinces)
        city = random.choice(province.cities)

        # Generate address
        address1 = self._generate_address()
        address2 = self._generate_area()

        # Generate zip code within range
        zip_code = self._generate_zip(province.zip_range)

        return CustomerAddress(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            address1=address1,
            address2=address2,
            city=city,
            province=province.name,
            province_code=province.code,
            zip=zip_code,
            country=self.auto_config.country,
            country_code=self.auto_config.country_code,
        )

    def _generate_email(self, first: str, last: str) -> str:
        """Generate a unique realistic email."""
        patterns = [
            f"{first.lower()}.{last.lower()}",
            f"{first.lower()}{random.randint(1, 999)}",
            f"{first.lower()}_{last.lower()}{random.randint(1, 99)}",
            f"{first.lower()}{last.lower()[:3]}{random.randint(10, 999)}",
            f"{first.lower()[0]}{last.lower()}{random.randint(1, 9999)}",
        ]
        base = random.choice(patterns)
        domain = random.choice(EMAIL_DOMAINS)
        email = f"{base}@{domain}"

        # Ensure uniqueness
        attempts = 0
        while email in self._used_emails and attempts < 50:
            suffix = ''.join(random.choices(string.digits, k=3))
            email = f"{base}{suffix}@{domain}"
            attempts += 1

        self._used_emails.add(email)
        return email

    def _generate_phone(self) -> str:
        """Generate a unique realistic Indian phone number."""
        # Indian mobile numbers: 10 digits starting with 6-9
        prefix = random.choice(["6", "7", "8", "9"])
        number = prefix + ''.join(random.choices(string.digits, k=9))

        attempts = 0
        while number in self._used_phones and attempts < 50:
            number = prefix + ''.join(random.choices(string.digits, k=9))
            attempts += 1

        self._used_phones.add(number)
        return number

    def _generate_address(self) -> str:
        """Generate a street address."""
        house_num = random.randint(1, 999)
        street = random.choice(STREET_PREFIXES)

        patterns = [
            f"{house_num}, {street}",
            f"House No. {house_num}, {street}",
            f"Flat {house_num}, {street}",
            f"{house_num}/{random.randint(1, 20)}, {street}",
            f"Plot {house_num}, {street}",
        ]
        return random.choice(patterns)

    def _generate_area(self) -> str:
        """Generate area/locality name."""
        names = [
            "Krishna", "Ram", "Shanti", "Prem", "Green", "Sun",
            "Golden", "Silver", "Royal", "Star", "New", "Old",
            "East", "West", "North", "South", "Central", "Model",
        ]
        name = random.choice(names)
        suffix = random.choice(AREA_SUFFIXES)
        return f"{name} {suffix}"

    def _generate_zip(self, zip_range: List[str]) -> str:
        """Generate zip code within a range."""
        if len(zip_range) >= 2:
            try:
                low = int(zip_range[0])
                high = int(zip_range[1])
                return str(random.randint(low, high))
            except ValueError:
                pass
        return "400001"
