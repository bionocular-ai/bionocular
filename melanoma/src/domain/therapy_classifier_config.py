"""Therapy approval status configuration.

This module contains the therapy classification data as a Python dictionary
for easy import without external dependencies.
"""

THERAPY_CONFIG = {
    "approved_therapies": {
        "immune_checkpoint_inhibitors": [
            {
                "name": "Pembrolizumab",
                "brand_name": "Keytruda",
                "status": "approved",
                "indications": [
                    "Adjuvant therapy for resected melanoma",
                    "First-line treatment for advanced melanoma",
                    "Standard comparator in trials",
                ],
            },
            {
                "name": "Nivolumab",
                "brand_name": "Opdivo",
                "status": "approved",
                "indications": [
                    "US-licensed and EU-authorized",
                    "Standard adjuvant therapy",
                ],
            },
            {"name": "Ipilimumab", "brand_name": "Yervoy", "status": "approved"},
            {
                "name": "Cemiplimab",
                "brand_name": "Libtayo",
                "status": "approved",
                "indications": [
                    "Cutaneous Squamous Cell Carcinoma (CSCC)",
                    "Basal Cell Carcinoma (BCC)",
                ],
            },
            {
                "name": "Avelumab",
                "brand_name": "Bavencio",
                "status": "approved",
                "indications": ["Merkel Cell Carcinoma"],
            },
            {"name": "Atezolizumab", "brand_name": "Tecentriq", "status": "approved"},
        ],
        "targeted_therapies": [
            {
                "name": "Dabrafenib + Trametinib",
                "brand_names": ["Tafinlar", "Mekinist"],
                "status": "approved",
            },
            {
                "name": "Vemurafenib + Cobimetinib",
                "brand_names": ["Zelboraf", "Cotellic"],
                "status": "approved",
            },
            {
                "name": "Encorafenib + Binimetinib",
                "brand_names": ["Braftovi", "Mektovi"],
                "status": "approved",
            },
        ],
        "chemotherapy": [
            {"name": "Dacarbazine", "status": "approved"},
            {"name": "Temozolomide", "status": "approved"},
            {"name": "Fotemustine", "status": "approved"},
        ],
        "local_therapies": [
            {
                "name": "T-VEC",
                "full_name": "Talimogene laherparepvec",
                "brand_name": "Imlygic",
                "status": "approved",
            },
            {"name": "Imiquimod", "status": "approved"},
            {"name": "Melphalan", "status": "approved"},
        ],
    },
    "investigational_therapies": {
        "novel_checkpoint_inhibitors": [
            {
                "name": "Relatlimab",
                "mechanism": "Anti-LAG-3",
                "status": "investigational",
            },
            {
                "name": "Fianlimab",
                "mechanism": "Anti-LAG-3",
                "status": "investigational",
            },
            {
                "name": "Tiragolumab",
                "mechanism": "Anti-TIGIT",
                "status": "investigational",
            },
            {
                "name": "Vibostolimab",
                "mechanism": "Anti-TIGIT",
                "status": "investigational",
            },
            {
                "name": "Quavonlimab",
                "alias": "Qmab",
                "mechanism": "Anti-CTLA-4",
                "status": "investigational",
            },
            {
                "name": "Gotistobart",
                "alias": "ONC-392",
                "mechanism": "Anti-CTLA-4",
                "status": "investigational",
            },
            {
                "name": "Domatinostat",
                "mechanism": "HDAC inhibitor",
                "status": "investigational",
            },
        ],
        "cell_therapies": [
            {"name": "Lifileucel", "alias": "LN-144", "status": "investigational"},
            {"name": "OBX-115", "status": "investigational"},
            {"name": "Tebentafusp", "alias": "IMCgp100", "status": "investigational"},
            {"name": "SCIB1", "status": "investigational"},
            {"name": "PRAME TCR/IL-15 NK Cells", "status": "investigational"},
        ],
        "vaccines": [
            {"name": "mRNA-4157", "alias": "V940", "status": "investigational"},
            {"name": "Seviprotimut-L", "status": "investigational"},
            {"name": "TLPLDC", "status": "investigational"},
            {"name": "IFx-Hu2.0", "status": "investigational"},
        ],
        "oncolytic_viruses": [
            {"name": "TILT-123", "status": "investigational"},
            {
                "name": "RP1",
                "full_name": "Vusolimogene oderparepvec",
                "status": "investigational",
            },
            {
                "name": "Daromun",
                "components": ["L19IL2", "L19TNF"],
                "status": "investigational",
            },
            {"name": "PV-10", "status": "investigational"},
        ],
        "small_molecules": [
            {"name": "Lenvatinib", "status": "investigational"},
            {"name": "Darovasertib", "alias": "IDE196", "status": "investigational"},
            {"name": "Sitravatinib", "status": "investigational"},
            {"name": "Ripretinib", "alias": "DCC-2618", "status": "investigational"},
            {"name": "Tunlametinib", "alias": "HL-085", "status": "investigational"},
            {"name": "Navtemadlin", "alias": "KRT-232", "status": "investigational"},
        ],
        "radiopharmaceuticals": [
            {"name": "212Pb-VMT01", "status": "investigational"},
            {"name": "225Ac-MTI-201", "status": "investigational"},
        ],
    },
    "control_arms": [
        "Placebo",
        "Standard of Care",
        "Investigator's Choice",
        "Investigator's Choice Chemotherapy",
        "Best Alternative Care",
        "Historical Systemic Therapies",
        "Observation",
        "No Systemic Therapy",
    ],
    "approved_indicators": [
        "US-licensed",
        "EU-authorized",
        "Standard of Care",
        "Standard",
        "Approved",
        "Historical",
    ],
    "investigational_indicators": [
        "Phase 1",
        "Phase I",
        "First-in-Human",
        "FIH",
        "Investigational",
        "Experimental",
        "Novel",
    ],
}
