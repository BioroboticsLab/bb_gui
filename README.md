# **bb_gui**
A browser-based interface for recording videos and running the Beesbook detection and tracking pipeline.

---

## **Installation**

### **1. Prerequisites**
To enable video recording, follow the setup instructions for **bb_imgacquisition** (Basler support branch).  
Refer to the installation guide: **[bb_imgacquisition Setup](https://github.com/BioroboticsLab/bb_imgacquisition/tree/basler_support)**  


### **2. Run the Setup Script**
Download the [Beesbook pipeline install script](https://github.com/BioroboticsLab/bb_main/blob/master/code/install_update_beesbook_pipeline.sh), and run the following command to install all dependencies and configure the environment:

```bash
bash install_update_beesbook_pipeline.sh
```

This script sets up Conda, installs TensorFlow, PyTorch, and all required packages, including bb_pipeline, bb_tracking, and bb_behavior.

### **3. Install bb_gui**
```bash
conda activate beesbook
pip install git+https://github.com/BioroboticsLab/bb_gui.git
```

## Usage

To launch, simply run:

```bash
conda activate beesbook
bb_gui
```

This will start the Streamlit interface and open it in your default web browser.

Since bb_gui wraps streamlit run bb_gui.py, you can pass any Streamlit options, for example:
```bb_gui --server.headless true --server.port 8501```