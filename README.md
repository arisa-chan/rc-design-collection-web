# 🏗️ ACI 318M-25 RC Design Collection

[![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/framework-Air-orange.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Beta Module](https://img.shields.io/badge/Beam_Design-v0.8_Beta-yellow)]()
[![Beta Module](https://img.shields.io/badge/Column_Design-v0.8_Beta-yellow)]()

A powerful Python web application built with the Air web framework for designing reinforced concrete members in accordance with **ACI 318M-25** provisions. 

Perform serviceability checks, generate reinforcement details, and calculate quantity takeoffs, all while ensuring code compliance, including constructability and seismic requirements. Best of all, since this is a web application, you can do the calculations on any device, anytime, anywhere, even while on the go.

## 🚀 Features & Modules

### 1. RC Beam Design `(v0.8 Beta)`
*Note: This module is currently in beta. Please try it out and report any feedback or issues!*

* **Detailed Elevation Views:** Visual representations of beam reinforcements.
* **Serviceability Checks:** Immediate live load and long-term deflection checks.
* **Reinforcement Details & Capacity:** * Automatically considers constructability requirements.
  * Automatically applies seismic detailing when required.
* **Quantity Takeoff:** Accurately considers hooks, bends, splices, and standard commercial bar lengths for precise material estimation.

### 2. RC Column Design `(v0.8 Beta)`
*Note: This module is currently in beta. Please try it out and report any feedback or issues!*

* **Detailed Elevation Views:** Visual representations of column reinforcements.
* **Reinforcement Details & Capacity:** * Automatically checks constructability requirements.
  * Adjusts for seismic detailing when applicable.
  * Includes checks for strong-column, weak-beam (SCWB) and joint shear.
* **Quantity Takeoff:** Accurately considers hooks, bends, splices, and standard commercial bar lengths for precise material estimation.

## 🛠️ Tech Stack

* **Language:** [Python](https://www.python.org/)
* **Web Framework:** [Air](https://airwebframework.org/) 
* **Dependency Management:** `uv` (via `uv.lock` & `pyproject.toml`)

## 💻 Installation & Local Setup

To run this application locally on your machine, follow these steps:

**1. Clone the repository**
```bash
git clone https://github.com/arisa-chan/rc-design-collection-web.git
cd rc-design-collection-web
```

**2. Set up a virtual environment (Optional but recommended)**
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
# Alternatively, if you use uv:
# uv pip install -r requirements.txt
```
Note that the latest version of Air requires Python 3.13 or 3.14 only.

**4. Run the application**
```bash
air run
```

## 📸 Screenshots

<details>
<summary><b>Click to expand screenshots</b></summary>
<br>

**Beam Design:**
![Serviceability Checks](img_1.png)
![Reinforcement Details](img_3.png)
![Quantity Takeoff](img_4.png)

**Column Design:**
![Elevation View](img_5.png)
![Column Details](img_6.png)
![Column Takeoff](img_7.png)

</details>

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! 
If you find a bug (especially in the Beta modules) or want to add a feature, please feel free to check the [issues page](https://github.com/arisa-chan/rc-design-collection-web/issues) or submit a Pull Request.

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more information.

---
*If you find this tool helpful in your engineering workflow, please consider giving it a ⭐!*
