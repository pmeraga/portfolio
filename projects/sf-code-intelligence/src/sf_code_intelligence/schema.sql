CREATE TABLE IF NOT EXISTS apex_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    sharing_model TEXT,
    raw_annotations TEXT
);

CREATE TABLE IF NOT EXISTS apex_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL REFERENCES apex_classes(class_name),
    method_name TEXT NOT NULL,
    return_type TEXT,
    annotations TEXT,
    is_static INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sobjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_name TEXT NOT NULL UNIQUE,
    label TEXT,
    file_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sobject_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_name TEXT NOT NULL REFERENCES sobjects(object_name),
    field_name TEXT NOT NULL,
    field_type TEXT,
    reference_to TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_name TEXT NOT NULL
);
