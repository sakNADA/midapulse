# ADR 0001: No biometric identification

Status: accepted

MidaPulse measures table states, not people. The system must not perform facial recognition, demographic inference, persistent person tracking, or identity matching. Raw frames remain on the edge device and are discarded after occupancy inference. The central API accepts only table ID, occupied/not occupied, confidence, timestamp, and source.

This boundary makes privacy testable in the API schema and reduces the impact of a central-system breach.

