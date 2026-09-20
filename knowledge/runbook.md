# Churn pipeline runbook

The customer-churn-training and customer-churn-scoring pipelines run daily. Validate schema and null checks before training, require the model promotion gate, and compare current feature distributions with the training reference. If a gate fails, retain the last approved model and investigate upstream changes.

