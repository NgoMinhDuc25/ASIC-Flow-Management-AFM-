"""
AFM - ASIC Flow Management

A lightweight, folder-based version-control system tailored for ASIC
Physical Design flows (Import -> Floorplan -> Placement -> CTS -> ...).

AFM is NOT an EDA tool. It manages:
    - Flow / step directory structure
    - Version + branch (clone) management inside a step
    - Naming and folder-content rules
    - Data lineage between steps ("jump step")

See ASIC_Flow_Management_Specification.docx / Software_Specification.docx
for the full design document this package implements.
"""

__version__ = "0.2.2"
