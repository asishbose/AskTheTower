##@ Stack (local compose)
.PHONY: up seed logs logs-save ps
up: ## Build and start mock, tower, binding, alerts, dynamodb-local; wait healthy; seed demo
	@deploy/compose/init-env.sh
	$(COMPOSE) up -d --build --wait --wait-timeout 600
	@$(MAKE) --no-print-directory seed
	@echo "stack up: Tower $(TOWER_URL) · binding $(BINDING_URL) · mock $(MOCK_URL) · alerts $(ALERTS_URL) — next: make demo"
seed: ## Reload scenarios/demo.yaml and the demo users/lines/grants (idempotent; runs in a container)
	@mkdir -p $(COMPOSE_LOGS)
	$(COMPOSE) --profile tools run --rm --no-deps -T seed 2>&1 | tee $(COMPOSE_LOGS)/seed.log; exit $${PIPESTATUS[0]}
logs: ## Tail local stack logs (Alerts' "SMS to=" lines are the phone buzz)
	$(COMPOSE) logs -f --tail=200
logs-save: ## Write the stack's logs to deploy/compose/logs/stack.log (the privacy grep reads it)
	@mkdir -p $(COMPOSE_LOGS)
	@$(COMPOSE) logs --no-color > $(COMPOSE_LOGS)/stack.log 2>&1 && echo "logs → $(COMPOSE_LOGS)/stack.log"
ps: ## Local stack status
	$(COMPOSE) ps
shell-%: ## Shell into a local service container, e.g. make shell-tower-mcp
	$(COMPOSE) exec $* /bin/sh
