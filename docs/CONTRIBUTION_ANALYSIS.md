# Contribution Analysis

RetailPulse uses contribution analysis as an arithmetic decomposition of additive metric changes, not as causal attribution.

Supported metrics: `gmv`, `pay_amount`.
Supported dimensions: `channel`, `region` (shipping province).

The implementation compares adjacent time windows and computes `delta_i = current_i - previous_i`, `net_contribution_share_i = delta_i / sum(delta_i)`, and movement share from absolute deltas. Negative contribution shares represent dimensions offsetting the net movement.
