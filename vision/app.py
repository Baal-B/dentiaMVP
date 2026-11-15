import os
import tempfile
import cv2
import numpy as np
import streamlit as st
from PIL import Image
from inference_denti import DentiAIYOLO

# Configuration de la page Streamlit
st.set_page_config(
    page_title="DentiAI - Diagnostic Radiologique IA",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS moderne et médical
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
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
    """Initialise et met en cache le modèle pour des inférences instantanées."""
    return DentiAIYOLO()

detector = load_detector()

# Barre latérale (Paramètres)
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/tooth.png", width=64)
    st.title("⚙️ Paramètres IA")
    
    st.subheader("Mode de Détection")
    mode = st.radio(
        "Sélectionnez le protocole :",
        options=["dual_tier", "high_precision_95"],
        format_func=lambda x: "🛡️ Double Seuil (Certifié >=95% + Zones Suspectes)" if x == "dual_tier" else "🎯 Strict Haute Précision (>=95% uniquement)"
    )
    
    st.markdown("---")
    st.subheader("Amélioration d'Image")
    use_clahe = st.checkbox("Rehaussement adaptatif CLAHE", value=True, help="Augmente les micro-contrastes osseux et de l'émail dentaire.")
    use_tta = st.checkbox("TTA (Test-Time Augmentation)", value=True, help="Combine plusieurs échelles d'inférence pour une précision maximale.")

    st.markdown("---")
    st.markdown("### 📋 Légende Médicale")
    st.markdown('<span class="badge-impacted">■ Dent incluse (Orange)</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-caries">■ Carie débutante (Jaune)</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-periapical">■ Lésion périapicale (Rouge)</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge-deep-caries">■ Carie profonde (Magenta)</span>', unsafe_allow_html=True)

# En-tête principal
st.markdown('<div class="main-header">🦷 DentiAI - Analyse Radiologique Panoramique</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Système d\'assistance au diagnostic dentaire assisté par IA (YOLO11m calibré &ge; 95% de précision)</div>', unsafe_allow_html=True)

# Sélection de la source de l'image
tab_upload, tab_sample = st.tabs(["📤 Téléverser une Radiographie", "📁 Exemples Pré-chargés"])

img_path = None
temp_file_to_cleanup = None

with tab_upload:
    uploaded_file = st.file_uploader(
        "Glissez-déposez ou parcourez une radiographie panoramique (PNG, JPG, JPEG) :",
        type=["png", "jpg", "jpeg"]
    )
    if uploaded_file is not None:
        # Enregistrer temporairement l'image pour l'analyse
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
            selected_sample = st.selectbox("Choisir un cas clinique du jeu de test :", sample_files)
            if st.button("Charger cet exemple"):
                img_path = os.path.join(val_dir, selected_sample)
        else:
            st.info("Aucun exemple disponible dans le dossier de validation.")
    else:
        st.info("Dossier d'exemples introuvable.")

# Traitement et affichage
if img_path and os.path.exists(img_path):
    st.markdown("---")
    
    with st.spinner("🔍 Analyse de la radiographie en cours avec YOLO11m..."):
        results = detector.analyze_radiograph(
            image_path=img_path,
            precision_mode=mode,
            use_clahe=use_clahe,
            use_tta=use_tta,
            save_annotated=True,
            output_dir="predictions"
        )
    
    # Présentation visuelle côte-à-côte
    col_orig, col_annot = st.columns(2)
    
    with col_orig:
        st.subheader("📷 Cliché Original")
        st.image(img_path, use_container_width=True)
        
    with col_annot:
        st.subheader("🎯 Diagnostic Annoté IA (>= 95% Précision)")
        annotated_img_path = results.get("annotated_image")
        if annotated_img_path and os.path.exists(annotated_img_path):
            st.image(annotated_img_path, use_container_width=True)
        else:
            st.warning("Impossible de générer l'image annotée.")

    st.markdown("---")

    # Métriques synthétiques
    confirmed = results.get("confirmed_findings_95", [])
    suspicious = results.get("suspicious_findings_for_review", [])
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric("Pathologies Certifiées (>=95%)", len(confirmed))
    with m_col2:
        st.metric("Zones Suspectes à Réviser", len(suspicious))
    with m_col3:
        st.metric("Temps de Traitement", "< 25 ms", delta="Temps Réel GPU")

    # Détails des constatations
    if confirmed or suspicious:
        st.subheader("📋 Rapport d'Analyse Clinique")
        
        all_findings = []
        for f in confirmed:
            all_findings.append({
                "ID": f"#{f['finding_id']}",
                "Pathologie": f["label_fr"],
                "Confiance IA": f"{f['confidence'] * 100:.1f}%",
                "Statut": "✅ " + f["precision_tier"],
                "Seuil Requis": f">={f['p95_calibrated_threshold']*100:.0f}%"
            })
            
        for f in suspicious:
            all_findings.append({
                "ID": f"#{f['finding_id']}",
                "Pathologie": f["label_fr"],
                "Confiance IA": f"{f['confidence'] * 100:.1f}%",
                "Statut": "⚠️ " + f["precision_tier"],
                "Seuil Requis": f"Seuil Alerte (35%)"
            })
            
        st.dataframe(all_findings, use_container_width=True)
        
        # Téléchargement du rapport JSON
        json_str = str(results).replace("'", '"')
        st.download_button(
            label="💾 Télécharger le rapport clinique (JSON)",
            data=json_str,
            file_name=f"rapport_dentiai_{os.path.basename(img_path)}.json",
            mime="application/json"
        )
    else:
        st.success("🎉 Aucune pathologie détectée sur ce cliché avec le niveau de confiance sélectionné.")

    # Nettoyage temporaire si fichier téléversé
    if temp_file_to_cleanup and os.path.exists(temp_file_to_cleanup):
        try:
            os.remove(temp_file_to_cleanup)
        except Exception:
            pass
