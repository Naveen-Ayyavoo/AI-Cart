"""
Category-aware clarification and search-criteria metadata for Purchase Contracts.

Resolves:
- Defect 6: Converts static `ambiguous_requirements` strings into contextual,
  optional interactive controls tailored to the actual product category.
- Defect 7: Supplies product-specific attribute presets, units, options, and
  exclusions for the Edit Search Criteria interface using backend contract data
  rather than fixed electronics placeholders.
"""

import re
from typing import Any

CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_clarification_text(value: str, max_length: int = 120) -> str:
    """Sanitize untrusted user clarification text server-side."""
    if not isinstance(value, str):
        return ""
    cleaned = CONTROL_CHAR_RE.sub(" ", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip()
    return cleaned


def _slugify_key(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return slug[:48] or "detail"


def detect_product_profile(category: str = "", description: str = "", prompt: str = "") -> str:
    """Detect canonical product domain profile from structured contract fields."""
    text = f"{category} {description} {prompt}".lower()

    if any(w in text for w in ["iphone", "galaxy", "pixel", "smartphone", "cell phone", "mobile phone", "pro max"]):
        return "smartphones"
    if any(w in text for w in ["headphone", "earphone", "earbud", "headset", "audio"]):
        return "headphones"
    if any(w in text for w in ["keyboard", "keychron", "tenkeyless", "tkl", "mechanical switch"]):
        return "keyboards"
    if any(w in text for w in ["laptop", "notebook", "macbook", "ultrabook", "thinkpad", "computer"]):
        return "laptops"
    if any(w in text for w in ["shoe", "sneaker", "boot", "footwear", "sandal", "running shoe"]):
        return "footwear"
    if any(w in text for w in ["pant", "trouser", "jean", "chino", "slack", "short", "legging"]):
        return "apparel_pants"
    if any(w in text for w in ["shirt", "jacket", "hoodie", "sweater", "coat", "dress", "apparel", "clothing"]):
        return "apparel_tops"
    if any(w in text for w in ["chair", "desk chair", "ergonomic chair", "stool", "sofa", "furniture"]):
        return "chairs"
    if any(
        w in text
        for w in [
            "blender",
            "coffee",
            "espresso",
            "kettle",
            "toaster",
            "air fryer",
            "cooker",
            "pan",
            "pot",
            "kitchen",
            "cookware",
        ]
    ):
        return "kitchen"
    return "general"


PROFILE_CLARIFICATION_CATALOG: dict[str, dict[str, dict[str, Any]]] = {
    "apparel_pants": {
        "size": {
            "key": "size",
            "label": "Size / Waist & Inseam",
            "control_type": "text",
            "placeholder": "e.g. 32x30, M, or L",
            "help_text": "Enter waist/inseam or standard letter size.",
        },
        "fit": {
            "key": "fit",
            "label": "Fit",
            "control_type": "select",
            "options": ["Slim", "Regular", "Relaxed", "Straight", "Athletic", "Other"],
            "help_text": "Optional preferred cut or fit.",
        },
        "material": {
            "key": "material",
            "label": "Fabric Material",
            "control_type": "select",
            "options": ["Cotton", "Denim", "Chino / Twill", "Linen", "Polyester Blend", "Wool", "Other"],
            "help_text": "Preferred fabric composition.",
        },
        "style": {
            "key": "style",
            "label": "Pant Style",
            "control_type": "select",
            "options": ["Chinos", "Jeans", "Dress Pants", "Joggers / Casual", "Cargo", "Other"],
            "help_text": "Preferred garment style.",
        },
    },
    "apparel_tops": {
        "size": {
            "key": "size",
            "label": "Garment Size",
            "control_type": "select",
            "options": ["XS", "S", "M", "L", "XL", "XXL", "Other"],
            "help_text": "Optional standard size.",
        },
        "fit": {
            "key": "fit",
            "label": "Fit",
            "control_type": "select",
            "options": ["Slim", "Regular", "Relaxed", "Oversized", "Other"],
            "help_text": "Preferred cut or silhouette.",
        },
        "material": {
            "key": "material",
            "label": "Material",
            "control_type": "select",
            "options": ["Cotton", "Leather", "Wool", "Linen", "Polyester Blend", "Fleece", "Other"],
            "help_text": "Preferred material.",
        },
        "style": {
            "key": "style",
            "label": "Style",
            "control_type": "text",
            "placeholder": "e.g. Crewneck, V-neck, Button-down",
            "help_text": "Optional neckline or garment style.",
        },
    },
    "footwear": {
        "size": {
            "key": "shoe_size",
            "label": "Shoe Size",
            "control_type": "number",
            "unit": "US",
            "min": "4",
            "max": "16",
            "step": "0.5",
            "placeholder": "e.g. 10.5",
            "help_text": "US shoe sizing (e.g. 9, 10.5).",
        },
        "width": {
            "key": "width",
            "label": "Shoe Width",
            "control_type": "select",
            "options": ["Narrow", "Standard (D/M)", "Wide (2E)", "Extra Wide (4E)", "Other"],
            "help_text": "Optional width preference.",
        },
        "material": {
            "key": "material",
            "label": "Upper Material",
            "control_type": "select",
            "options": ["Leather", "Breathable Mesh", "Canvas", "Suede", "Synthetic", "Other"],
            "help_text": "Preferred shoe upper material.",
        },
    },
    "smartphones": {
        "condition": {
            "key": "condition",
            "label": "Condition",
            "control_type": "select",
            "options": ["Refurbished", "New", "Renewed / Certified", "Open-box", "Other"],
            "help_text": "Preferred device condition.",
        },
        "storage": {
            "key": "storage",
            "label": "Storage capacity",
            "control_type": "select",
            "options": ["128 GB", "256 GB", "512 GB", "1 TB", "Other"],
            "help_text": "Preferred internal storage capacity.",
        },
        "carrier": {
            "key": "carrier",
            "label": "Carrier lock status",
            "control_type": "select",
            "options": ["Unlocked", "Carrier-locked", "Other"],
            "help_text": "Preferred carrier compatibility.",
        },
    },
    "headphones": {
        "connectivity": {
            "key": "connectivity",
            "label": "Connectivity",
            "control_type": "select",
            "options": ["Wireless (Bluetooth)", "Wired (3.5mm / USB-C)", "Hybrid (Wireless + Wired)", "Other"],
            "help_text": "Preferred connection method.",
        },
        "form_factor": {
            "key": "form_factor",
            "label": "Fit / Form Factor",
            "control_type": "select",
            "options": ["Over-Ear", "On-Ear", "In-Ear (Earbuds)", "Other"],
            "help_text": "How the headphones rest on your ears.",
        },
        "noise_cancelling": {
            "key": "noise_cancelling",
            "label": "Noise Cancellation",
            "control_type": "select",
            "options": ["Active Noise Canceling (ANC)", "Passive Isolation", "Transparency / Open-Back", "Other"],
            "help_text": "Preferred sound isolation behavior.",
        },
        "codec": {
            "key": "audio_codec",
            "label": "Preferred Audio Codec",
            "control_type": "select",
            "options": ["AAC (Apple / Universal)", "aptX / aptX HD", "LDAC (High-Res Android)", "Standard SBC / No preference", "Other"],
            "help_text": "Optional Bluetooth audio codec support.",
        },
        "battery": {
            "key": "battery_life",
            "label": "Minimum Battery Life",
            "control_type": "number",
            "unit": "hours",
            "min": "1",
            "max": "120",
            "step": "1",
            "placeholder": "e.g. 30",
            "help_text": "Desired playback hours per charge.",
        },
    },
    "laptops": {
        "ram": {
            "key": "ram",
            "label": "Memory (RAM)",
            "control_type": "select",
            "options": ["8 GB", "16 GB", "32 GB", "64 GB+", "Other"],
            "help_text": "Preferred system memory capacity.",
        },
        "storage": {
            "key": "storage",
            "label": "Storage (SSD)",
            "control_type": "select",
            "options": ["256 GB SSD", "512 GB SSD", "1 TB SSD", "2 TB+ SSD", "Other"],
            "help_text": "Preferred solid-state drive capacity.",
        },
        "screen_size": {
            "key": "screen_size",
            "label": "Screen Size",
            "control_type": "select",
            "options": ["13–14 inch (Ultraportable)", "15–16 inch (Standard)", "17+ inch (Workstation)", "Other"],
            "help_text": "Preferred display diagonal size.",
        },
        "workload": {
            "key": "workload",
            "label": "Intended Workload",
            "control_type": "text",
            "placeholder": "e.g. Software development, video editing, everyday web browsing",
            "help_text": "Helps prioritize CPU, RAM, and battery needs.",
        },
    },
    "keyboards": {
        "switch_brand": {
            "key": "switch_brand",
            "label": "Switch Brand / Feel",
            "control_type": "select",
            "options": ["Cherry MX", "Gateron", "Outemu", "Tactile (Any Brand)", "Linear / Quiet (Any Brand)", "Other"],
            "help_text": "Optional preferred mechanical switch manufacturer or feel.",
        },
        "layout": {
            "key": "layout",
            "label": "Keyboard Layout",
            "control_type": "select",
            "options": ["Tenkeyless (TKL)", "75% Compact", "Full-Size (100%)", "60% / 65% Compact", "Other"],
            "help_text": "Size and presence of number pad / function row.",
        },
        "wrist_rest": {
            "key": "wrist_rest",
            "label": "Wrist Rest",
            "control_type": "select",
            "options": ["Included", "Not Required", "Detachable / Padded"],
            "help_text": "Whether a matching wrist rest should be included.",
        },
    },
    "chairs": {
        "headrest": {
            "key": "headrest",
            "label": "Headrest Preference",
            "control_type": "select",
            "options": ["Integrated Headrest", "Optional / No Headrest", "Adjustable Headrest"],
            "help_text": "Preferred neck and upper back support.",
        },
        "material": {
            "key": "material",
            "label": "Seat & Back Material",
            "control_type": "select",
            "options": ["Breathable Mesh", "Fabric Cushion", "Leather / Faux Leather", "Other"],
            "help_text": "Preferred upholstery material.",
        },
        "lumbar": {
            "key": "lumbar_support",
            "label": "Lumbar Support",
            "control_type": "select",
            "options": ["Adjustable Lumbar", "Fixed Ergonomic Curve", "Other"],
            "help_text": "Lower back support configuration.",
        },
    },
    "kitchen": {
        "capacity": {
            "key": "capacity",
            "label": "Capacity / Volume",
            "control_type": "text",
            "placeholder": "e.g. 6 Quart, 1.7 Liters, or 12 Cups",
            "help_text": "Specify container or batch capacity with units.",
        },
        "dimensions": {
            "key": "dimensions",
            "label": "Dimensions / Countertop Footprint",
            "control_type": "text",
            "placeholder": "e.g. Under 14 inches tall",
            "help_text": "Optional physical space constraint.",
        },
        "material": {
            "key": "material",
            "label": "Primary Material",
            "control_type": "select",
            "options": ["Stainless Steel", "Cast Iron", "Glass", "Ceramic / Non-Stick", "BPA-Free Plastic", "Other"],
            "help_text": "Preferred food-contact or body material.",
        },
    },
}


PROFILE_EDIT_METADATA: dict[str, dict[str, Any]] = {
    "apparel_pants": {
        "profile_label": "Apparel — Pants & Bottoms",
        "attr_placeholder": "e.g. size, fit, material, color",
        "val_placeholder": "e.g. 32x30, Slim, Cotton",
        "excl_placeholder": "e.g. dry-clean only, used, pleated",
        "recommended_attributes": [
            {"key": "size", "label": "Size", "suggestions": ["30x30", "32x30", "32x32", "34x32", "M", "L"]},
            {"key": "fit", "label": "Fit", "suggestions": ["Slim", "Regular", "Relaxed", "Straight"]},
            {"key": "material", "label": "Material", "suggestions": ["Cotton", "Denim", "Twill", "Linen"]},
            {"key": "color", "label": "Color", "suggestions": ["Red", "Navy", "Black", "Khaki"]},
        ],
        "common_exclusions": ["used", "dry-clean only", "distressed", "polyester-only"],
    },
    "apparel_tops": {
        "profile_label": "Apparel — Tops & Outerwear",
        "attr_placeholder": "e.g. size, fit, material, sleeve",
        "val_placeholder": "e.g. Medium, Regular, Cotton",
        "excl_placeholder": "e.g. used, wool, sleeveless",
        "recommended_attributes": [
            {"key": "size", "label": "Size", "suggestions": ["S", "M", "L", "XL", "XXL"]},
            {"key": "fit", "label": "Fit", "suggestions": ["Slim", "Regular", "Relaxed", "Oversized"]},
            {"key": "material", "label": "Material", "suggestions": ["Cotton", "Leather", "Linen", "Fleece"]},
            {"key": "color", "label": "Color", "suggestions": ["Black", "Navy", "White", "Olive"]},
        ],
        "common_exclusions": ["used", "dry-clean only", "cropped"],
    },
    "footwear": {
        "profile_label": "Footwear & Shoes",
        "attr_placeholder": "e.g. shoe_size, width, material, activity",
        "val_placeholder": "e.g. 10.5 US, Wide, Breathable Mesh",
        "excl_placeholder": "e.g. used, leather, cleats",
        "recommended_attributes": [
            {"key": "shoe_size", "label": "US Size", "suggestions": ["8", "9", "10", "10.5", "11", "12"]},
            {"key": "width", "label": "Width", "suggestions": ["Standard (D/M)", "Wide (2E)", "Narrow"]},
            {"key": "material", "label": "Material", "suggestions": ["Leather", "Mesh", "Canvas", "Suede"]},
            {"key": "activity", "label": "Use", "suggestions": ["Running", "Walking", "Casual", "Trail"]},
        ],
        "common_exclusions": ["used", "refurbished", "high-heel", "cleats"],
    },
    "smartphones": {
        "profile_label": "Smartphones & Mobile Devices",
        "attr_placeholder": "e.g. condition, storage, carrier, color",
        "val_placeholder": "e.g. Refurbished, 256 GB, Unlocked",
        "excl_placeholder": "e.g. carrier-locked, cracked screen, parts-only",
        "recommended_attributes": [
            {"key": "condition", "label": "Condition", "suggestions": ["Refurbished", "New", "Renewed"]},
            {"key": "storage", "label": "Storage", "suggestions": ["128 GB", "256 GB", "512 GB", "1 TB"]},
            {"key": "carrier", "label": "Carrier", "suggestions": ["Unlocked"]},
            {"key": "color", "label": "Colour", "suggestions": ["Black Titanium", "Natural Titanium", "White"]},
        ],
        "common_exclusions": ["carrier-locked", "parts-only", "damaged"],
    },
    "headphones": {
        "profile_label": "Audio & Headphones",
        "attr_placeholder": "e.g. connectivity, noise_cancelling, form_factor",
        "val_placeholder": "e.g. Bluetooth, Active, Over-Ear",
        "excl_placeholder": "e.g. wired-only, refurbished, on-ear",
        "recommended_attributes": [
            {"key": "connectivity", "label": "Connectivity", "suggestions": ["Bluetooth", "Wired", "USB-C"]},
            {"key": "form_factor", "label": "Form Factor", "suggestions": ["Over-Ear", "In-Ear", "On-Ear"]},
            {"key": "noise_cancelling", "label": "Noise Canceling", "suggestions": ["Active", "Passive"]},
            {"key": "battery_life", "label": "Battery Life", "suggestions": [">= 20 hours", ">= 30 hours", ">= 40 hours"]},
        ],
        "common_exclusions": ["wired-only", "refurbished", "on-ear", "used"],
    },
    "laptops": {
        "profile_label": "Laptops & Computers",
        "attr_placeholder": "e.g. ram, storage, screen_size, cpu",
        "val_placeholder": "e.g. 16 GB, 512 GB SSD, 14 inch",
        "excl_placeholder": "e.g. refurbished, chromebook, used",
        "recommended_attributes": [
            {"key": "ram", "label": "RAM", "suggestions": ["16 GB", "32 GB", "8 GB"]},
            {"key": "storage", "label": "Storage", "suggestions": ["512 GB SSD", "1 TB SSD", "256 GB SSD"]},
            {"key": "screen_size", "label": "Screen Size", "suggestions": ["14 inch", "15.6 inch", "16 inch"]},
            {"key": "workload", "label": "Workload", "suggestions": ["Coding", "Office / Study", "Creative / Video"]},
        ],
        "common_exclusions": ["refurbished", "used", "chromebook", "renewed"],
    },
    "keyboards": {
        "profile_label": "Mechanical Keyboards & Peripherals",
        "attr_placeholder": "e.g. switch_type, layout, connection",
        "val_placeholder": "e.g. Tactile, Tenkeyless (TKL), USB-C",
        "excl_placeholder": "e.g. membrane, used, refurbished",
        "recommended_attributes": [
            {"key": "switch_type", "label": "Switch Type", "suggestions": ["Mechanical", "Tactile Brown", "Linear Red"]},
            {"key": "layout", "label": "Layout", "suggestions": ["Tenkeyless (TKL)", "75% Compact", "Full-Size"]},
            {"key": "connection", "label": "Connection", "suggestions": ["Wireless Bluetooth", "Detachable USB-C"]},
            {"key": "backlight", "label": "Backlight", "suggestions": ["RGB", "White LED", "None"]},
        ],
        "common_exclusions": ["membrane", "used", "refurbished"],
    },
    "chairs": {
        "profile_label": "Office & Ergonomic Chairs",
        "attr_placeholder": "e.g. material, lumbar_support, armrests",
        "val_placeholder": "e.g. Breathable Mesh, Adjustable, 3D",
        "excl_placeholder": "e.g. bonded leather, gaming style, used",
        "recommended_attributes": [
            {"key": "material", "label": "Material", "suggestions": ["Breathable Mesh", "Fabric", "Leather"]},
            {"key": "lumbar_support", "label": "Lumbar", "suggestions": ["Adjustable", "Dynamic"]},
            {"key": "armrests", "label": "Armrests", "suggestions": ["3D Adjustable", "4D Adjustable", "Fixed"]},
            {"key": "headrest", "label": "Headrest", "suggestions": ["Integrated", "Optional"]},
        ],
        "common_exclusions": ["bonded leather", "gaming style", "used"],
    },
    "kitchen": {
        "profile_label": "Kitchen & Home Appliances",
        "attr_placeholder": "e.g. capacity, material, dimensions",
        "val_placeholder": "e.g. 6 Quart, Stainless Steel",
        "excl_placeholder": "e.g. non-stick PTFE, plastic, used",
        "recommended_attributes": [
            {"key": "material", "label": "Material", "suggestions": ["Stainless Steel", "Cast Iron", "Glass"]},
            {"key": "capacity", "label": "Capacity", "suggestions": ["4 Quart", "6 Quart", "1.7 Liters"]},
            {"key": "dishwasher_safe", "label": "Care", "suggestions": ["Dishwasher Safe", "Hand Wash"]},
        ],
        "common_exclusions": ["used", "refurbished", "PTFE"],
    },
    "general": {
        "profile_label": "Product Requirements",
        "attr_placeholder": "e.g. brand, size, color, material",
        "val_placeholder": "e.g. preferred feature or measurement",
        "excl_placeholder": "e.g. used, refurbished, damaged box",
        "recommended_attributes": [
            {"key": "brand", "label": "Brand", "suggestions": ["Any Verified Brand"]},
            {"key": "condition", "label": "Condition", "suggestions": ["New"]},
            {"key": "color", "label": "Color", "suggestions": ["Black", "Silver", "Neutral"]},
        ],
        "common_exclusions": ["used", "refurbished", "damaged"],
    },
}


def _match_ambiguity_template(raw_amb: str, profile: str) -> dict[str, Any]:
    """Match an ambiguity string against profile catalog or synthesize an intelligent control."""
    low = raw_amb.lower().strip()
    catalog = PROFILE_CLARIFICATION_CATALOG.get(profile, {})

    # Direct match inside the detected product profile
    keyword_map = {
        "size": ["size", "waist", "inseam", "dimension"],
        "shoe_size": ["shoe size", "us size", "eu size", "size"],
        "width": ["width"],
        "fit": ["fit", "form factor", "over-ear", "on-ear", "cut"],
        "form_factor": ["form factor", "over-ear", "on-ear", "in-ear", "fit"],
        "material": ["material", "fabric", "cloth", "leather", "mesh", "cotton"],
        "style": ["style", "cut", "design", "neckline"],
        "connectivity": ["connectivity", "wireless", "bluetooth", "wired", "connection"],
        "noise_cancelling": ["noise", "anc", "cancellation"],
        "codec": ["codec", "aac", "aptx", "ldac"],
        "battery": ["battery", "hours", "runtime"],
        "ram": ["ram", "memory"],
        "storage": ["storage", "ssd", "drive", "capacity"],
        "screen_size": ["screen", "display", "inch"],
        "workload": ["workload", "usage", "purpose", "use case"],
        "switch_brand": ["switch brand", "switch", "cherry", "gateron", "outemu"],
        "layout": ["layout", "tenkeyless", "full-size", "compact"],
        "wrist_rest": ["wrist rest", "palm rest"],
        "headrest": ["headrest"],
        "lumbar": ["lumbar"],
        "capacity": ["capacity", "volume", "quart", "liter", "cup"],
        "dimensions": ["dimension", "width", "height", "depth"],
    }

    for catalog_key, spec in catalog.items():
        triggers = keyword_map.get(catalog_key, [catalog_key.replace("_", " ")])
        if any(t in low for t in triggers):
            return dict(spec)

    # Generic contextual inference when ambiguity isn't in the preset catalog
    clean_label = re.sub(r"\bnot specified\b|\bunchosen\b|\bmissing\b", "", low).strip(" :-()").title()
    if not clean_label:
        clean_label = raw_amb.strip().capitalize()

    if any(w in low for w in ["color", "colour", "shade", "finish"]):
        return {
            "key": "color",
            "label": "Color / Finish",
            "control_type": "select",
            "options": ["Black", "White", "Silver / Grey", "Blue / Navy", "Red", "Other"],
            "help_text": "Optional preferred color or finish.",
        }

    # Numeric unit detection (e.g. weight, battery hours, screen inches, capacity)
    unit_hints = [
        (["battery", "hour"], "hours", "1", "200", "1", "e.g. 20"),
        (["weight", "lbs", "pound"], "lbs", "1", "1000", "1", "e.g. 250"),
        (["inch", "screen", "display"], "inches", "5", "100", "0.1", "e.g. 15.6"),
        (["gb", "ram", "memory"], "GB", "2", "512", "1", "e.g. 16"),
        (["watt", "power"], "W", "1", "5000", "1", "e.g. 65"),
    ]
    for words, unit, min_v, max_v, step_v, ph in unit_hints:
        if any(w in low for w in words):
            return {
                "key": _slugify_key(clean_label),
                "label": clean_label,
                "control_type": "number",
                "unit": unit,
                "min": min_v,
                "max": max_v,
                "step": step_v,
                "placeholder": ph,
                "help_text": f"Optional numeric target ({unit}).",
            }

    return {
        "key": _slugify_key(clean_label),
        "label": clean_label,
        "control_type": "text",
        "placeholder": f"Specify {clean_label.lower()} (optional)",
        "help_text": f"Optional preference for: {raw_amb}",
    }


def build_clarification_fields(contract) -> list[dict[str, Any]]:
    """
    Generate contextual, category-grounded optional clarification controls
    for a PurchaseContract.
    Never shows irrelevant defaults like apparel material/fit/size on non-apparel.
    """
    profile = detect_product_profile(
        contract.category,
        contract.product_description,
        contract.raw_prompt,
    )
    existing_prefs = contract.preferred_specs or {}
    existing_reqs = contract.required_specs or {}

    fields: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for idx, raw_amb in enumerate(contract.ambiguous_requirements or []):
        spec = _match_ambiguity_template(str(raw_amb), profile)
        key = spec["key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)

        current_val = ""
        if key in existing_prefs:
            current_val = str(existing_prefs[key])
        elif key in existing_reqs:
            current_val = str(existing_reqs[key])

        options = spec.get("options", [])
        custom_val = ""
        select_val = current_val
        if spec["control_type"] == "select" and current_val and current_val not in options and "Other" in options:
            select_val = "Other"
            custom_val = current_val

        fields.append(
            {
                "index": idx,
                "field_name": f"clarify__{key}",
                "custom_field_name": f"clarify_custom__{key}",
                "requirement_toggle_name": f"clarify_required__{key}",
                "input_id": f"id_clarify_{key}_{idx}",
                "key": key,
                "label": spec["label"],
                "raw_ambiguity": raw_amb,
                "control_type": spec["control_type"],
                "options": options,
                "unit": spec.get("unit", ""),
                "min": spec.get("min", ""),
                "max": spec.get("max", ""),
                "step": spec.get("step", "any"),
                "placeholder": spec.get("placeholder", ""),
                "help_text": spec.get("help_text", ""),
                "current_value": current_val,
                "select_value": select_val,
                "custom_value": custom_val,
                "is_required_spec": key in existing_reqs,
                "is_resolved": bool(current_val),
            }
        )

    return fields


def build_edit_criteria_metadata(contract) -> dict[str, Any]:
    """
    Build product-specific metadata for the Edit Search Criteria form
    using backend contract/category information.
    """
    profile = detect_product_profile(
        contract.category,
        contract.product_description,
        contract.raw_prompt,
    )
    meta = dict(PROFILE_EDIT_METADATA.get(profile, PROFILE_EDIT_METADATA["general"]))
    meta["profile"] = profile
    return meta
