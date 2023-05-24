from __future__ import annotations
from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship, backref, mapped_column, Mapped, DeclarativeBase
from sqlalchemy.sql.sqltypes import Boolean

VERSION = "1.0.0"


class Base(DeclarativeBase):
    pass


document__tag = Table(
    "document__tag",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("document.ID"), primary_key=True),
    Column("link_tag",  Integer, ForeignKey("tag.ID"), primary_key=True),
)


document__author = Table(
    "document__author",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("document.ID"), primary_key=True),
    Column("author_id",  Integer, ForeignKey("person.ID"), primary_key=True),
)


folder__folder = Table(
    "folder__folder",
    Base.metadata,
    Column("parent_id", Integer, ForeignKey("folder.ID"), primary_key=True),
    Column("child_id",  Integer, ForeignKey("folder.ID"), primary_key=True),
)


class Person(Base):
    __tablename__ = "person"
    ID          = Column(Integer, primary_key=True)
    name        = Column(String)
    display_name = Column(String)
    contact     = relationship("PersonContact", backref=backref("person"))
    authored    = relationship(
        "Document", secondary=document__author, back_populates="authors"
    )


class PersonContact(Base):
    __tablename__ = "person_contact"
    ID          = Column(Integer, primary_key=True)
    person_id   = Column(Integer, ForeignKey("person.ID"))
    method      = Column(String)
    data        = Column(String)


class Group(Base):
    __tablename__ = "group"
    ID          = Column(Integer, primary_key=True)
    name        = Column(String)
    versions    = relationship("GroupV", backref=backref("group"))


class GroupV(Base):
    __tablename__ = "group_version"
    ID          = Column(Integer, primary_key=True)
    group_id    = Column(Integer, ForeignKey("group.ID"))
    version     = Column(String)
    folders     = relationship("Folder", backref=backref("group_version"))
    documents   = relationship("Document", backref=backref("group_version"))


class Tag(Base):
    __tablename__ = "tag"
    ID          = Column(Integer, primary_key=True)
    name        = Column(String)
    documents   = relationship(
        "Document", secondary=document__tag, back_populates="tags"
    )


class Folder(Base):
    __tablename__ = "folder"
    ID          = Column(Integer, primary_key=True)
    group_version_id = Column(Integer, ForeignKey("group_version.ID"))
    name        = Column(String)
    path        = Column(String)
    documents   = relationship("Document", backref=backref("folder"))
    parent      = relationship(
        "Folder", secondary=folder__folder,
        primaryjoin  =folder__folder.c.parent_id==ID,
        secondaryjoin=folder__folder.c.child_id==ID,
        backref="folders"
    )


class Document(Base):
    __tablename__ = "document"
    ID          = Column(Integer, primary_key=True)
    group_version_id = Column(Integer, ForeignKey("group_version.ID"))
    folder_id   = Column(Integer, ForeignKey("folder.ID"))
    name        = Column(String)
    path        = Column(String)
    doc_id      = Column(String)
    type        = Column(String)
    title       = Column(String)
    timestamp   = Column(Integer)
    date        = Column(String)
    modified_at = Column(String)
    readonly    = Column(Boolean)
    import_en   = Column(Boolean)
    data_yaml   = Column(String)
    content     = Column(String)
    # refs        = relationship("Link", backref=backref("source"), foreign_keys=["link.source_id"])     # All links from this doc
    refbacks    = relationship("Link", backref=backref("target"))     # All links that are referring to this doc
    blob        = relationship("Blob", backref=backref("document"))
    tags        = relationship(
        "Tag", secondary=document__tag, back_populates="documents"
    )
    authors     = relationship(
        "Person", secondary=document__author, back_populates="authored"
    )


class Link(Base):
    __tablename__ = "link"
    ID          = Column(Integer, primary_key=True)
    full        = Column(String)
    text        = Column(String)
    objid       = Column(String)
    section     = Column(String)
    source_id   = Column(Integer)
    target_id   = Column(Integer, ForeignKey("document.ID"))


class Blob(Base):
    __tablename__ = "blob"
    ID          = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("document.ID"))
    path        = Column(String)
    data        = Column(String)
