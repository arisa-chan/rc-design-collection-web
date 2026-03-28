# ACI 318M-25 RC Design Collection
A Python web application for designing reinforced concrete members according to ACI 318M-25 provisions. Written using Air web framework.

## Currently implemented modules

### RC beam design (v0.8 beta)

> [!NOTE]
> This module is in beta. Please try this out and let me know your experience using this. Thanks!

  - Serviceability checks
    ![img_1.png](img_1.png)
  - Reinforcement details and capacity checks
    - automatically considers constructability requirements
    - automatically considers seismic detailing when required
    ![img_3.png](img_3.png)
  - Quantity takeoff
    - considers hooks, bends, splices, and commercial bar lengths
    ![img_4.png](img_4.png)

### RC column design (v0.4 alpha)

> [!WARNING]
> The refinement of this module is ongoing. Please anticipate bugs, wrong results and/or missing features.

- Detailed elevation view of reinforcements
    ![img_5.png](img_5.png)
- Reinforcement details and capacity checks
    - automatically considers constructability requirements
    - automatically considers seismic detailing when required
    ![img_6.png](img_6.png)
- Quantity takeoff
    - considers hooks, bends, splices, and commercial bar lengths
    ![img_7.png](img_7.png)
