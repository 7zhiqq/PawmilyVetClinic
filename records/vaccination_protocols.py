from dataclasses import dataclass
from datetime import date, timedelta
import calendar
import re
from decimal import Decimal


@dataclass(frozen=True)
class VaccinationProtocol:
    code: str
    name: str
    species: str
    aliases: tuple[str, ...]
    primary_weeks: tuple[int, ...] = ()
    maintenance_days: int | None = None
    maintenance_months: int | None = None
    fallback_series_interval_days: int | None = None


def add_months(base_date: date, months: int) -> date:
    """Add months while clamping day to the destination month's length."""
    month_index = (base_date.month - 1) + months
    target_year = base_date.year + (month_index // 12)
    target_month = (month_index % 12) + 1
    max_day = calendar.monthrange(target_year, target_month)[1]
    return date(target_year, target_month, min(base_date.day, max_day))


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


PROTOCOLS = {
    "dog": (
        VaccinationProtocol(
            code="dog_5in1",
            name="5-in-1 Vaccine",
            species="dog",
            aliases=("dhpp", "5 in 1", "5-in-1", "dapp", "distemper"),
            primary_weeks=(6, 8, 10, 12, 16),
            maintenance_days=365,
            fallback_series_interval_days=14,
        ),
        VaccinationProtocol(
            code="dog_rabies",
            name="Rabies Vaccine",
            species="dog",
            aliases=("rabies dog", "rabies"),
            primary_weeks=(12,),
            maintenance_days=365,
        ),
        VaccinationProtocol(
            code="dog_bordetella",
            name="Kennel Cough (Bordetella)",
            species="dog",
            aliases=("bordetella", "kennel cough"),
            primary_weeks=(8,),
            maintenance_days=365,
        ),
        VaccinationProtocol(
            code="dog_coronavirus",
            name="Coronavirus",
            species="dog",
            aliases=("canine coronavirus", "coronavirus"),
            primary_weeks=(6, 9),
            maintenance_days=365,
            fallback_series_interval_days=21,
        ),
        VaccinationProtocol(
            code="dog_deworming",
            name="Deworming",
            species="dog",
            aliases=("deworm", "deworming"),
            primary_weeks=(2, 4, 6, 8, 10, 12),
            maintenance_months=3,
            fallback_series_interval_days=14,
        ),
        VaccinationProtocol(
            code="dog_tick_flea",
            name="Tick & Flea Prevention",
            species="dog",
            aliases=("tick flea", "flea", "tick and flea", "ecto"),
            primary_weeks=(6,),
            maintenance_months=1,
        ),
    ),
    "cat": (
        VaccinationProtocol(
            code="cat_fvrcp",
            name="FVRCP Vaccine",
            species="cat",
            aliases=("fvrcp", "panleukopenia", "calicivirus", "rhinotracheitis"),
            primary_weeks=(6, 10, 14),
            maintenance_days=365,
            fallback_series_interval_days=28,
        ),
        VaccinationProtocol(
            code="cat_rabies",
            name="Rabies Vaccine",
            species="cat",
            aliases=("rabies cat", "rabies"),
            primary_weeks=(12,),
            maintenance_days=365,
        ),
        VaccinationProtocol(
            code="cat_felv",
            name="Feline Leukemia (FeLV)",
            species="cat",
            aliases=("felv", "feline leukemia"),
            primary_weeks=(8, 12),
            maintenance_days=365,
            fallback_series_interval_days=28,
        ),
        VaccinationProtocol(
            code="cat_deworming",
            name="Deworming",
            species="cat",
            aliases=("deworm", "deworming"),
            primary_weeks=(2, 4, 6, 8, 10, 12),
            maintenance_months=3,
            fallback_series_interval_days=14,
        ),
        VaccinationProtocol(
            code="cat_tick_flea",
            name="Tick & Flea Prevention",
            species="cat",
            aliases=("tick flea", "flea", "tick and flea", "ecto"),
            primary_weeks=(6,),
            maintenance_months=1,
        ),
    ),
}


PROTOCOL_PRICES_PHP = {
    "dog": {
        "5-in-1 Vaccine": Decimal("850.00"),
        "Rabies Vaccine": Decimal("450.00"),
        "Kennel Cough (Bordetella)": Decimal("650.00"),
        "Coronavirus": Decimal("600.00"),
        "Deworming": Decimal("250.00"),
        "Tick & Flea Prevention": Decimal("300.00"),
    },
    "cat": {
        "FVRCP Vaccine": Decimal("800.00"),
        "Rabies Vaccine": Decimal("450.00"),
        "Feline Leukemia (FeLV)": Decimal("900.00"),
        "Deworming": Decimal("250.00"),
        "Tick & Flea Prevention": Decimal("300.00"),
    },
}


def find_protocol(species: str | None, *names: str | None) -> VaccinationProtocol | None:
    protocols = PROTOCOLS.get((species or "").lower(), ())
    if not protocols:
        return None

    normalized_names = {_normalize_name(name) for name in names if name}
    normalized_names.discard("")
    if not normalized_names:
        return None

    for protocol in protocols:
        candidates = {_normalize_name(protocol.name), *(_normalize_name(alias) for alias in protocol.aliases)}
        if normalized_names.intersection(candidates):
            return protocol

    for protocol in protocols:
        candidates = [_normalize_name(protocol.name), *(_normalize_name(alias) for alias in protocol.aliases)]
        for incoming in normalized_names:
            if any(incoming and (incoming in candidate or candidate in incoming) for candidate in candidates):
                return protocol
    return None


def compute_next_due_date(
    protocol: VaccinationProtocol,
    birth_date: date | None,
    date_administered: date,
    prior_dose_dates: list[date],
) -> date | None:
    """
    Compute next due date based on species protocol, birth date, and dose history.
    """
    if birth_date and protocol.primary_weeks:
        staged_due_dates = [
            birth_date + timedelta(days=week * 7)
            for week in protocol.primary_weeks
        ]
        for due_date in staged_due_dates:
            if due_date > date_administered:
                return due_date

    total_doses = len(prior_dose_dates) + 1
    if protocol.primary_weeks and total_doses < len(protocol.primary_weeks):
        interval = protocol.fallback_series_interval_days or 14
        return date_administered + timedelta(days=interval)

    if protocol.maintenance_months:
        return add_months(date_administered, protocol.maintenance_months)
    if protocol.maintenance_days:
        return date_administered + timedelta(days=protocol.maintenance_days)
    return None


def protocol_catalog_for_species(species: str | None) -> tuple[VaccinationProtocol, ...]:
    return tuple(PROTOCOLS.get((species or "").lower(), ()))


def protocol_price_for_species(species: str | None, vaccine_name: str | None) -> Decimal:
    species_key = (species or "").lower()
    if not vaccine_name:
        return Decimal("0.00")
    return PROTOCOL_PRICES_PHP.get(species_key, {}).get(vaccine_name, Decimal("0.00"))


def protocol_price_map_for_species(species: str | None) -> dict[str, Decimal]:
    return dict(PROTOCOL_PRICES_PHP.get((species or "").lower(), {}))


def protocol_schedule_summary(protocol: VaccinationProtocol) -> str:
    parts = []
    if protocol.primary_weeks:
        weeks = ", ".join(str(week) for week in protocol.primary_weeks)
        parts.append(f"Primary series at {weeks} weeks")

    if protocol.maintenance_months:
        month_label = "month" if protocol.maintenance_months == 1 else "months"
        parts.append(f"then every {protocol.maintenance_months} {month_label}")
    elif protocol.maintenance_days:
        if protocol.maintenance_days == 365:
            parts.append("then yearly booster")
        else:
            day_label = "day" if protocol.maintenance_days == 1 else "days"
            parts.append(f"then every {protocol.maintenance_days} {day_label}")

    return ", ".join(parts) if parts else "No default schedule set."


def schedule_reference_for_vaccine(
    species: str | None,
    vaccine_name: str | None,
    *,
    description: str = "",
    booster_interval_days: int | None = None,
) -> str:
    cleaned_description = (description or "").strip()
    if cleaned_description:
        return cleaned_description

    protocol = find_protocol(species, vaccine_name)
    if protocol:
        return protocol_schedule_summary(protocol)

    if booster_interval_days:
        day_label = "day" if booster_interval_days == 1 else "days"
        return f"Booster every {booster_interval_days} {day_label}."

    return "No default schedule set."
