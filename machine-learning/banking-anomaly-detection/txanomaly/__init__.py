"""txanomaly: card and payment fraud detection, evaluated like a fraud team.

    data       synthetic transactions with five labelled fraud typologies
    features   behavioural features computed strictly from each customer's past
    models     rules, Isolation Forest, logistic regression, gradient boosting
    evaluate   temporal split, alert budget, loss prevented, customer bootstrap
    explain    reason codes for every alert
"""

__version__ = "1.0.0"
