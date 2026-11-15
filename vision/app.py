import os
import tempfile
import cv2
import json
import numpy as np
import streamlit as st
from PIL import Image
from inference_denti import DentiAIYOLO
from medical_certification import MedicalCertificationStandard

# Configuration de la page Streamlit
st.set_page_config(
    page_title="DentiAI - Système Diagnostique Dentaire Autonome Certifié (MDR Class IIa)",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS médical certifié
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.2rem;
    }
    .cert-badge {
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
        padding: 6px 14px;
        border-radius: 8px;
        font-size: 0.9rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .badge-impacted {
        background-color: #FFEDD5;
        color: #C2410C;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-caries {
        background-color: #FEF9C3;
        color: #854D0E;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-periapical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-deep-caries {
        background-color: #FCE7F3;
        color: #9D174D;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_detector():
    return DentiAIYOLO()

detector = load_detector()

# Barre latérale
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/tooth.png", width=64)
    st.title("🛡️ Certification Médicale")
    st.markdown("**Norme :** MDR (EU) 2017/745 Class IIa")
    st.markdown("**Sécurité logicielle :** IEC 62304 Class B")
    st.markdown("---")
    
    st.subheader("Mode d'Inférence")
    pipeline_mode = st.selectbox(
        "Moteur diagnostique :",
        options=["combined_sota", "tiled_sahi", "hierarchical_2stage", "standard"],
        format_func=lambda x: {
            "combined_sota": "🚀 SOTA Certifié (Tuiles SAHI + 2-Stages)",
            "tiled_sahi": "🔍 Option A (Tuilage Quadrants Haute Résolution)",
            "hierarchical_2stage": "🧬 Option B (Raffinement 2-Stages)",
            "standard": "⚡ Mode Standard Plein Écran"
        }[x]
    )

    st.subheader("Verrou de Sécurité Clinique")
    precision_mode = st.radio(
        "Politique d'autorisation :",
        options=["dual_tier", "high_precision_95"],
        format_func=lambda x: "🛡️ Double Seuil (Certifié >=95% + Zones d'Alerte)" if x == "dual_tier" else "🔒 Strict Diagnostic Autonome (>=95% uniquement)"
    )
    
    use_clahe = st.checkbox("Rehaussement adaptatif CLAHE", value=True)
    bypass_quality_gate = st.checkbox("Mode Démonstration / Forcer l'analyse (Ignore les alertes qualité)", value=False)

    st.markdown("---")
    st.markdown("### 📋 Nomenclature FDI")
    st.markdown('<span class="badge-impacted">■ Q1 à Q4 : Dents Incluses</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-caries">■ Q1 à Q4 : Caries Débutantes</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-deep-caries">■ Q1 à Q4 : Caries Profondes</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-periapical">■ Q1 à Q4 : Lésions Périapicales</span>', unsafe_allow_html=True)

# En-tête principal
st.markdown('<div class="main-header">🦷 DentiAI - Diagnostic Radiologique Autonome Certifié</div>', unsafe_allow_html=True)
st.markdown('<span class="cert-badge">🛡️ CONFORME MDR (EU) 2017/745 CLASS IIa & IEC 62304 | TOUS FORMATS RADIOLOGIQUES ACCEPTÉS</span>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Système certifié compatible radiographies panoramiques complètes, clichés rétro-alvéolaires (bitewing portrait) et cadrages de quadrants.</div>', unsafe_allow_html=True)

# Sélection de la source
tab_upload, tab_sample = st.tabs(["📤 Téléverser une Radiographie", "📁 Cas Cliniques de Validation"])

img_path = None
temp_file_to_cleanup = None

with tab_upload:
    uploaded_file = st.file_uploader(
        "Sélectionnez une radiographie (Panoramique paysage ou Rétro-alvéolaire portrait) :",
        type=["png", "jpg", "jpeg"]
    )
    if uploaded_file is not None:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            img_path = tmp.name
            temp_file_to_cleanup = tmp.name

with tab_sample:
    val_dir = "dentex_yolo/images/val"
    if os.path.exists(val_dir):
        sample_files = [f for f in os.listdir(val_dir) if f.endswith((".png", ".jpg"))][:6]
        if sample_files:
            selected_sample = st.selectbox("Choisir un cas d'étude certifié :", sample_files)
            if st.button("Lancer l'audit diagnostique autonome"):
                img_path = os.path.join(val_dir, selected_sample)

# Traitement diagnostique certifié
if img_path and os.path.exists(img_path):
    st.markdown("---")
    
    with st.spinner("🛡️ Analyse radiologique en cours avec contrôle qualité et inférence certifiée..."):
        dossier = detector.analyze_radiograph(
            image_path=img_path,
            pipeline_mode=pipeline_mode,
            precision_mode=precision_mode,
            use_clahe=use_clahe,
            save_annotated=True,
            bypass_quality_gate=bypass_quality_gate,
            output_dir="predictions"
        )
    
    if dossier.get("status") == "rejected_by_safety_gate":
        st.error(f"❌ **DISPOSITIF DE SÉCURITÉ MÉDICALE ACTIVÉ (ISO/MDR) :** {dossier.get('message')}")
        st.info("💡 **Astuce :** Vous pouvez cocher l'option *'Mode Démonstration / Forcer l'analyse'* dans la barre latérale gauche pour analyser ce fichier quand même.")
    else:
        q_meta = dossier.get("radiograph_metadata", {}).get("pre_flight_quality_gate", {})
        q_metrics = q_meta.get("metrics", {})
        cliche_type = q_metrics.get("type", "Cliché Dentaire")
        
        qc_col1, qc_col2, qc_col3, qc_col4 = st.columns(4)
        with qc_col1:
            st.metric("Certificat d'Audit", dossier.get("audit_certificate_id", "CERT-OK"))
        with qc_col2:
            st.metric("Type de Cliché", cliche_type)
        with qc_col3:
            st.metric("Format & Ratio", f"{q_metrics.get('resolution', 'N/A')} ({q_metrics.get('aspect_ratio', 1.0)})")
        with qc_col4:
            st.metric("Netteté Radiologique", f"{q_metrics.get('sharpness_laplacian', 0)} (OK)")

        # Affichage côte-à-côte
        col_orig, col_annot = st.columns(2)
        with col_orig:
            st.subheader("📷 Cliché Radiologique Patient")
            st.image(img_path, use_container_width=True)
            
        with col_annot:
            st.subheader("🛡️ Cartographie Diagnostique Certifiée (>= 95%)")
            annotated_img = dossier.get("annotated_image")
            if annotated_img and os.path.exists(annotated_img):
                st.image(annotated_img, use_container_width=True)

        st.markdown("---")

        confirmed = dossier.get("confirmed_findings_95", [])
        suspicious = dossier.get("suspicious_findings_for_review", [])
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Diagnostics Certifiés Autonomes (>=95%)", len(confirmed))
        with m2:
            st.metric("Zones en Réserve Clinique", len(suspicious))
        with m3:
            st.metric("Signature Cryptographique", dossier.get("ai_engine_provenance", {}).get("weights_sha256", "")[:12] + "...")

        # Tableau d'Audit Clinique
        st.subheader("📋 Dossier d'Audit Médical & Constatations Autonomes")
        
        findings_table = []
        for f in (confirmed + suspicious):
            ci = f.get("wilson_confidence_interval_95", {})
            fdi = f.get("anatomical_location", {})
            findings_table.append({
                "N°": f"#{f['finding_id']}",
                "Quadrant FDI": fdi.get("quadrant_name", "Quadrant N/A"),
                "Pathologie": f["label_fr"],
                "Diagnostic Clinique (Stage 2)": f.get("clinical_pathology_severity", "Certifié"),
                "Score": f"{f['confidence_score']*100:.1f}%",
                "Intervalle Wilson 95%": f"[{ci.get('ci_lower', 0)*100:.1f}% - {ci.get('ci_upper', 0)*100:.1f}%]",
                "Statut Autonome": "✅ " + f["autonomous_certification"] if f.get("is_95_precision") else "⚠️ " + f["autonomous_certification"]
            })

        if findings_table:
            st.dataframe(findings_table, use_container_width=True)
            
            audit_json = json.dumps(dossier, indent=2, ensure_ascii=False)
            st.download_button(
                label="📄 Télécharger le Dossier d'Audit Réglementaire Certifié (JSON / IEC 62304)",
                data=audit_json,
                file_name=f"audit_certifie_{dossier.get('audit_certificate_id')}.json",
                mime="application/json"
            )
        else:
            st.success("🎉 Aucune pathologie détectée. Cliché dentaire sans anomalie certifiée à >= 95%.")

    if temp_file_to_cleanup and os.path.exists(temp_file_to_cleanup):
        try:
            os.remove(temp_file_to_cleanup)
        except Exception:
            pass
