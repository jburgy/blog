# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "sqlalchemy>=1.4",
# ]
# ///

""" SQLAlchemy version of store.py """

from sqlalchemy import Column, ForeignKey, Integer, JSON
from sqlalchemy import create_engine, func, literal_column, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# define models
class Patch(DeclarativeBase):
    __tablename__ = "patch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    inserted_at = Column(
        Integer, nullable=False, server_default=func.strftime('%s', 'now')
    )
    previous_id = Column(
        Integer,
        ForeignKey("patch.id", ondelete="SET DEFAULT"),
        nullable=False,
        server_default="0",
    )
    patch = Column(JSON)

    def __repr__(self) -> str:
        return f"<Patch(id={self.id}, inserted_at={self.inserted_at}, previous_id={
            self.previous_id}, patch={self.patch})>"


engine = create_engine("sqlite://", echo=True, future=True)
Session = sessionmaker(bind=engine, future=True)
session = Session()

session.bulk_save_objects([
    Patch(previous_id=0, patch=dict(a=1)),  # id=1
    Patch(previous_id=1, patch=dict(b=2, c=4)),  # id=2
    Patch(previous_id=2, patch=dict(a=3)),  # id=3
    Patch(previous_id=3, patch=dict(c=None)),  # id=4
])
print(*session.execute(select(Patch)), sep="\n")

# Reconstruct object from patches like you would in lisp
head = select(
    literal_column("0").label("id"),
    literal_column("'{}'").label("object"),
).cte(name="assemble", recursive=True)
tail = select(
    Patch.id,
    func.json_patch(head.c.object, Patch.patch)
).select_from(Patch).join(
    head,
    Patch.previous_id == head.c.id
)
assemble = head.union_all(tail)

statement = select(assemble).order_by(assemble.c.id.desc())
print(session.execute(statement).first())
