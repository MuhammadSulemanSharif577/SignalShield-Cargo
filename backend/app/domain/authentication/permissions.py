"""Backend-owned permission keys shared by authorization and role validation."""

PERMISSIONS = frozenset({
    "dashboard:view", "tracking:view",
    "users:view", "users:manage",
    "roles:manage", "settings:manage", "audit:view",
    "vehicles:view", "vehicles:manage",
    "drivers:view", "drivers:manage", "drivers:credentials",
    "journeys:view", "journeys:manage", "shipments:view", "shipments:manage",
    "warehouse:view", "warehouse:manage", "gnss:view", "analysis:view",
    "alerts:view", "alerts:manage", "incidents:view", "incidents:manage",
    "reports:operational", "reports:security",
})
