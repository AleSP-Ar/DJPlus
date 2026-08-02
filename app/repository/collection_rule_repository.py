from app.database import SessionLocal
from app.database.models import Collection, CollectionRule


class CollectionRuleRepository:
    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def create_rule(self, collection_id, field, operator, value):
        self._require_smart_collection(collection_id)
        rule = CollectionRule(collection_id=collection_id, field=field, operator=operator, value=str(value))
        self.session.add(rule)
        self.session.commit()
        return rule

    def delete_rule(self, rule_id):
        rule = self.session.get(CollectionRule, rule_id)
        if rule is None:
            raise ValueError("La regla no existe.")
        self.session.delete(rule)
        self.session.commit()

    def list_rules(self, collection_id):
        self._require_smart_collection(collection_id)
        return self.session.query(CollectionRule).filter(CollectionRule.collection_id == collection_id).order_by(CollectionRule.id.asc()).all()

    def close(self):
        self.session.close()

    def _require_smart_collection(self, collection_id):
        collection = self.session.get(Collection, collection_id)
        if collection is None:
            raise ValueError("La colección no existe.")
        if collection.type != "smart":
            raise ValueError("Las reglas solo se permiten en colecciones smart.")
        return collection
