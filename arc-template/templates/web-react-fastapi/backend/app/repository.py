from .models import ModuleSummary


class InMemoryRepository:
    def __init__(self) -> None:
        self._modules: dict[str, ModuleSummary] = {}

    def list_modules(self) -> list[ModuleSummary]:
        return list(self._modules.values())

    def upsert_module(self, module: ModuleSummary) -> ModuleSummary:
        self._modules[module.id] = module
        return module


repository = InMemoryRepository()
repository.upsert_module(ModuleSummary(id="home", name="Home"))

