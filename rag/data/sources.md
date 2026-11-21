# Sources of the DentIA RAG corpus

Generated on 2026-11-21 by `python -m dentia_rag.make_sources`. Do not edit by hand: change the manifests, then run the command again.

## 1. Documents added by hand (PDF)

22 documents. A licence marked `TO CHECK` must be verified before the corpus is shared outside the team: the PDFs themselves are **not** stored in Git.

| File | Title | Organization | Year | Type | Licence | Pages excluded |
|---|---|---|---|---|---|---|
| 01HEN35WFCSEYXXEWMHBMM28YG.pdf | Treatment of pulpal and apical disease: ESE S3-level clinical practice guideline | European Society of Endodontology | - | guideline | TO CHECK | 50-58 |
| 3rd-molar-guidelines--April-2021-v2.pdf | Third molar guidelines (April 2021) | - | 2021 | guideline | TO CHECK | 2,54-63,69,73,77,86-91,95,98-99,109-110 |
| 784_2025_Article_6727.pdf | Deep caries management: EFCD-ESE-ORCA S3-level clinical practice guideline | EFCD / ESE / ORCA | 2025 | guideline | TO CHECK | 17-19 |
| PIIS0002817718304690.pdf | Evidence-based clinical practice guideline on nonrestorative treatments for carious lesions | American Dental Association | 2018 | guideline | TO CHECK | 12-13,17-27,29-32 |
| PIIS0002817723002581.pdf | Evidence-based clinical practice guideline on restorative treatments for caries lesions | American Dental Association | 2023 | guideline | TO CHECK | 14-16,18-20,28-67 |
| guidance-on-the-extraction-of-wisdom-teeth-pdf-63732983749.pdf | Guidance on the extraction of wisdom teeth | NICE | 2000 | guideline | TO CHECK | 2-3,11-13 |
| manual\000551659.pdf | Deep Caries Management: EFCD-ESE-ORCA S3-Level Clinical Practice Guideline | EFCD / ESE / ORCA | 2026 | guideline | TO CHECK | 17-19 |
| manual\9789240116948-eng.pdf | WHO guideline on environmentally friendly and less invasive oral health care for preventing and managing dental caries | World Health Organization | - | guideline | TO CHECK | 1-9,57-68 |
| manual\A-tooth-autotransplantation-cost-model-for-pediatr.pdf | A tooth autotransplantation cost model for pediatric through young adult patients | TO CHECK | - | article | TO CHECK | 10-15 |
| manual\Antibiotic-stewardship--balancing-patient-care-and.pdf | Antibiotic stewardship: balancing patient care and public health | TO CHECK | - | article | TO CHECK | - |
| manual\Dental-care-during-pregnancy_adaj.pdf | Dental care during pregnancy | TO CHECK | - | article | TO CHECK | - |
| manual\Oral-assessment-of-patients-with-X-linked-hypophos.pdf | Oral assessment of patients with X-linked hypophosphatemic rickets | TO CHECK | - | article | TO CHECK | 7-8 |
| manual\Oral-virome-in-health-and-disease_2026_adaj.pdf | Oral virome in health and disease | TO CHECK | - | article | TO CHECK | 11-13 |
| manual\Smart-peptide–based-materials-and-their-clinical-a.pdf | Smart peptide-based materials and their clinical application for caries management | TO CHECK | - | article | TO CHECK | 11-13 |
| manual\Two-cases-of-tooth-resorption-in-patients-receivin.pdf | Two cases of tooth resorption in patients receiving denosumab therapy | TO CHECK | - | article | TO CHECK | 9-10 |
| manual\g_non-vpt.pdf | Non-Vital Pulp Therapy: AAPD Clinical Practice Guideline | American Academy of Pediatric Dentistry | 2020 | guideline | TO CHECK | 12-13 |
| manual\g_sdf.pdf | Use of Silver Diamine Fluoride for Dental Caries Management: AAPD Clinical Practice Guideline | American Academy of Pediatric Dentistry | 2017 | guideline | TO CHECK | 7,10-11 |
| manual\gao-et-al-2016-clinical-trials-of-silver-diamine-fluoride-in-arresting-caries-among-children-a-systematic-review.pdf | Clinical Trials of Silver Diamine Fluoride in Arresting Caries among Children | TO CHECK | - | article | TO CHECK | 9-10 |
| manual\piis0002817716304731-sealants-cpg.pdf | Evidence-based clinical practice guideline for the use of pit-and-fissure sealants | American Dental Association | 2016 | guideline | TO CHECK | 10-23 |
| manual\s3.pdf | Vital Pulp Therapy Guideline: AAPD Clinical Practice Guideline (supersedes the 2017 guideline) | American Academy of Pediatric Dentistry | 2024 | guideline | TO CHECK | 13-14 |
| manual\s6.pdf | Nonpharmacological Behavior Guidance for the Pediatric Dental Patient: AAPD Clinical Practice Guideline | American Academy of Pediatric Dentistry | 2023 | guideline | TO CHECK | 18-26 |
| nihms-2209137.pdf | ADA/AAOMR patient selection for dental radiography and CBCT: clinical recommendations | ADA / AAOMR | - | guideline | TO CHECK | 1-3,14-29 |

## 2. Documents collected from Europe PMC (open access)

4538 documents: 0 with full text, 4538 abstract only. Each one is open access; its own licence is kept in `data/registry.csv` (column `license`) and in the chunk metadata (`url`, `doi`, `pmid`).

Source: Europe PMC REST API (https://europepmc.org/RestfulWebService).

### By evidence type

| Value | Documents |
|---|---|
| review | 1508 |
| article | 1206 |
| systematic_review | 1113 |
| rct | 361 |
| guideline | 320 |
| case_report | 30 |

### By licence

| Value | Documents |
|---|---|
| cc by | 3107 |
| cc by-nc | 605 |
| cc by-nc-nd | 493 |
| cc by-nc-sa | 163 |
| open access (license not given) | 134 |
| cc0 | 24 |
| cc by-nd | 12 |

### By topic

| Value | Documents |
|---|---|
| guidelines | 736 |
| caries | 320 |
| endodontics | 320 |
| periodontal | 320 |
| implants | 320 |
| surgery | 320 |
| antibiotics | 320 |
| radiology | 320 |
| orthodontics | 320 |
| third_molar | 316 |
| restorative | 314 |
| pediatric | 307 |
| ai_dental | 305 |

### By publication year

| Value | Documents |
|---|---|
| 2026 | 522 |
| 2025 | 295 |
| 2014 | 279 |
| 2015 | 279 |
| 2016 | 279 |
| 2017 | 279 |
| 2018 | 279 |
| 2019 | 279 |
| 2020 | 279 |
| 2021 | 279 |
| 2022 | 279 |
| 2023 | 279 |
| 2024 | 279 |
| 2013 | 267 |
| 2012 | 253 |
| 2006 | 19 |
| 2007 | 19 |
| 2008 | 19 |
| 2009 | 19 |
| 2010 | 19 |
| 2011 | 19 |
| 2005 | 17 |
| 2027 | 1 |

## 3. Web pages

None yet. Add them with `python -m dentia_rag.collect add-urls data/urls.csv`.
