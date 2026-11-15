# 🦷 DentiAI - Support de Présentation (Module Vision)

Ce document résume les **2 diapositives de présentation** relatives au module de Vision par Ordinateur du projet DentiAI, avec le contenu des slides, les notes de discours oral et les prompts de génération automatique.

---

## 📊 Diapositive 1 : Architecture & Réalisations du Module

### Contenu de la Slide
* **Titre :** Module Vision DentiAI : Du Modèle à l'Interface Praticien
* **Sous-titre :** Pipeline complet de détection automatique des pathologies sur radiographies panoramiques (DENTEX)
* **Points Clés :**
  * **Architecture IA :** Entraînement de **YOLO11m** (20 millions de paramètres) sur le dataset médical de référence **DENTEX**.
  * **4 pathologies ciblées :** Dents incluses, Caries débutantes, Caries profondes et Lésions périapicales.
  * **Performance & Vitesse :** Analyse complète en **$< 25\text{ ms}$** par cliché sur GPU local (RTX 2050), temps réel.
  * **Interface Web Interactive (Streamlit) :** Application développée (`vision/app.py`) permettant le téléversement d'une radio, la visualisation annotée côte-à-côte et l'export du rapport clinique en JSON.

### 🎙️ Discours Oral Suggéré (~30 secondes)
> *"Dans ce projet d'équipe, j'ai développé l'intégralité du module de vision par ordinateur. Nous sommes partis du dataset DENTEX pour entraîner un modèle YOLO11m capable de détecter quatre pathologies dentaires majeures en moins de 25 millisecondes. Pour rendre ce travail immédiatement testable par l'équipe et les praticiens, j'ai également conçu une interface web interactive qui permet de glisser une radiographie et d'obtenir le diagnostic instantané avec un rapport clinique exportable."*

---

## 🎯 Diapositive 2 : Améliorations & Garantie $\ge 95\%$ de Précision

### Contenu de la Slide
* **Titre :** Optimisations Cliniques : Atteinte du Seuil de $\ge 95\%$ de Précision
* **Sous-titre :** Élimination des faux positifs et fiabilisation diagnostique
* **Points Clés :**
  * **Seuils Cliniques Calibrés :** Détermination empirique des seuils à partir de la courbe Précision-Rappel :
    * **Dents incluses :** Seuil `0.78` $\rightarrow$ **$95.2\%$ à $100\%$ de précision**
    * **Caries débutantes :** Seuil `0.72` $\rightarrow$ **$\ge 95.0\%$ de précision**
    * **Caries profondes :** Seuil `0.80` $\rightarrow$ **$\ge 95.0\%$ de précision**
    * **Lésions périapicales :** Seuil `0.91` $\rightarrow$ **$\ge 95.0\%$ de précision**
  * **Arbitrage Inter-Classes (Cross-Class NMS) :** Résolution des ambiguïtés anatomiques (fusion/arbitrage entre carie simple et profonde sur une même dent).
  * **Prétraitement Adaptatif CLAHE :** Rehaussement dynamique des micro-contrastes osseux et de l'émail dentaire.
  * **Intégration d'Équipe :** Code source, modèle pré-entraîné, interface web et tests validés et synchronisés sur GitHub (`feature/vision-module`).

### 🎙️ Discours Oral Suggéré (~35 secondes)
> *"Au départ, les petites caries et les lésions périapicales présentaient des taux de précision plus faibles à cause de la ressemblance visuelle entre les stades d'évolution. Pour garantir les 95% de précision exigés en milieu médical, nous avons apporté trois améliorations majeures : un calibrage rigoureux des seuils de décision par pathologie, un filtre intelligent qui supprime les conflits entre carie superficielle et profonde sur une même dent, et un rehaussement de contraste CLAHE. Le module est aujourd'hui optimisé, validé et synchronisé avec le reste de l'équipe sur GitHub."*

---

## 🤖 Prompt de Génération Automatique (Gamma, Canva, ChatGPT)

```text
Génère 2 diapositives professionnelles, synthétiques et modernes en français pour une présentation de projet d'IA médicale dentaire :

Diapositive 1 :
Titre : Module Vision DentiAI : Du Modèle à l'Interface Praticien
Contenu :
- Entraînement de YOLO11m (20M paramètres) sur le dataset panoramique DENTEX.
- Détection de 4 pathologies : Dents incluses, Caries, Caries profondes, Lésions périapicales.
- Performance temps réel : Inférence en < 25 ms par radiographie.
- Interface Web Streamlit : Démonstrateur interactif avec upload, comparaison avant/après et export de rapport clinique JSON.

Diapositive 2 :
Titre : Optimisations Cliniques : Atteinte du Seuil de >= 95% de Précision
Contenu :
- Calibrage des seuils cliniques pour garantir >= 95% de précision sur chacune des 4 pathologies.
- Algorithme Cross-Class NMS : Résolution des ambiguïtés anatomiques entre caries débutantes et profondes sur la même dent.
- Prétraitement CLAHE adaptatif : Amélioration du contraste des micro-lésions osseuses et coronaires.
- Intégration d'équipe : Code, modèle entraîné et interface livrés sur GitHub (branche feature/vision-module).

Style : Médical, épuré, bullet points courts avec métriques mises en avant.
```
