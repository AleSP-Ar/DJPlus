from app.repository.collection_rule_repository import CollectionRuleRepository
from app.services.collection_service import CollectionService
from app.services.library_service import LibraryService
from app.services.smart_rule_engine import SmartRuleEngine


class SmartCollectionService:
    """Application service for smart collection rules and evaluation."""

    def __init__(self, collection_service=None, rule_repository=None, library_service=None, rule_engine=None):
        self.collection_service = collection_service or CollectionService()
        self.rule_repository = rule_repository or CollectionRuleRepository()
        self.library_service = library_service or LibraryService()
        self.rule_engine = rule_engine or SmartRuleEngine()

    def create_smart_collection(self, name, rules=(), description=None):
        rules = list(rules)
        self.rule_engine.build_filters([self._rule_data(rule) for rule in rules])
        collection = self.collection_service.create_smart_collection(name, description=description)
        for rule in rules:
            self.rule_repository.create_rule(
                collection.id,
                rule["field"],
                rule["operator"],
                rule["value"],
            )
        return collection

    def add_rule(self, collection_id, field, operator, value):
        rules = self.list_rules(collection_id)
        proposed_rule = {"field": field, "operator": operator, "value": value}
        self.rule_engine.build_filters([*rules, self._rule_data(proposed_rule)])
        return self.rule_repository.create_rule(collection_id, field, operator, value)

    def delete_rule(self, rule_id):
        return self.rule_repository.delete_rule(rule_id)

    def list_rules(self, collection_id):
        return self.rule_repository.list_rules(collection_id)

    def evaluate(self, collection_id):
        rules = self.list_rules(collection_id)
        criteria = self.rule_engine.build_filters(rules)
        tracks, has_more = self.library_service.apply_filter_criteria(criteria)
        return tracks, has_more, self.library_service.count_results()

    def close(self):
        self.rule_repository.close()
        self.library_service.close()

    def _rule_data(self, rule):
        if isinstance(rule, dict):
            return type("RuleData", (), rule)()
        return rule
