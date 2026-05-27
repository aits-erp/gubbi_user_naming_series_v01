import json

import frappe
from frappe import _
from frappe.utils import cstr

SETTINGS_DOCTYPE = "User Naming Series"
DETAIL_DOCTYPE = "User Naming Series Detail"
SETTINGS_TABLE_FIELD = "naming_series_rules"
SERIES_FIELD = "naming_series"


def boot_session(bootinfo):
	bootinfo.user_naming_series_rules = get_user_series_map()


def restrict_reportview_by_series():
	cmd = cstr(frappe.local.form_dict.get("cmd"))
	if not cmd and getattr(frappe.local, "request", None):
		path = cstr(frappe.local.request.path)
		if "/api/method/" in path:
			cmd = path.rsplit("/api/method/", 1)[-1]

	if cmd not in {
		"frappe.desk.reportview.get",
		"frappe.desk.reportview.get_list",
		"frappe.desk.reportview.get_count",
		"frappe.desk.reportview.export_query",
		"frappe.desk.reportview.get_sidebar_stats",
		"frappe.desk.reportview.get_filter_dashboard_data",
	}:
		return

	doctype = cstr(frappe.local.form_dict.get("doctype")).strip()
	allowed = get_user_series_map().get(doctype)
	if not allowed:
		return

	frappe.local.form_dict["filters"] = frappe.as_json(
		_add_series_filter(doctype, frappe.local.form_dict.get("filters"), allowed)
	)


@frappe.whitelist()
def get_user_series_map():
	user = frappe.session.user
	if not user or user == "Guest" or not _settings_tables_exist():
		return {}

	parents = frappe.get_all(SETTINGS_DOCTYPE, filters={"user": user}, pluck="name")
	if not parents:
		return {}

	rows = frappe.get_all(
		DETAIL_DOCTYPE,
		filters={"parent": ["in", parents], "parenttype": SETTINGS_DOCTYPE},
		fields=["document_type", SERIES_FIELD],
		order_by="parent asc, idx asc",
	)

	rules = {}
	for row in rows:
		doctype = cstr(row.document_type).strip()
		series = cstr(row.naming_series).strip()
		if doctype and series:
			rules.setdefault(doctype, [])
			if series not in rules[doctype]:
				rules[doctype].append(series)

	return rules


def apply_user_naming_series(doc, method=None):
	if not _should_enforce(doc):
		return

	allowed = get_user_series_map().get(doc.doctype)
	if not allowed:
		return

	current = cstr(doc.get(SERIES_FIELD)).strip()
	if not current or len(allowed) == 1:
		doc.set(SERIES_FIELD, allowed[0])


def validate_user_naming_series(doc, method=None):
	if not _should_enforce(doc):
		return

	allowed = get_user_series_map().get(doc.doctype)
	if not allowed:
		return

	current = cstr(doc.get(SERIES_FIELD)).strip()
	if not current:
		doc.set(SERIES_FIELD, allowed[0])
		return

	if current not in allowed:
		frappe.throw(
			_("{0} is not an allowed naming series for {1}. Allowed: {2}").format(
				frappe.bold(current),
				frappe.bold(doc.doctype),
				", ".join(allowed),
			)
		)


def _add_series_filter(doctype, filters, allowed):
	filters = _normalize_filters(doctype, filters)
	filters.append([doctype, SERIES_FIELD, "in", allowed])
	return filters


def _normalize_filters(doctype, filters):
	if not filters:
		return []

	if isinstance(filters, str):
		filters = json.loads(filters)

	if not filters:
		return []

	if isinstance(filters, dict):
		normalized = []
		for fieldname, value in filters.items():
			if isinstance(value, (list, tuple)) and len(value) > 1:
				normalized.append([doctype, fieldname, value[0], value[1]])
			else:
				normalized.append([doctype, fieldname, "=", value])
		return normalized

	return list(filters)


def validate_settings_doc(doc):
	_validate_unique_user(doc)
	seen = set()

	for row in doc.get(SETTINGS_TABLE_FIELD) or []:
		row.document_type = cstr(row.document_type).strip()
		row.naming_series = cstr(row.naming_series).strip()

		if not row.document_type or not row.naming_series:
			frappe.throw(_("Document Type and Naming Series are required in row {0}.").format(row.idx))

		valid_series = get_doctype_naming_series(row.document_type)
		if not valid_series:
			frappe.throw(
				_("{0} does not have a naming_series field with configured options.").format(
					frappe.bold(row.document_type)
				)
			)

		if row.naming_series not in valid_series:
			frappe.throw(
				_("{0} is not a valid naming series for {1}. Valid series: {2}").format(
					frappe.bold(row.naming_series),
					frappe.bold(row.document_type),
					", ".join(valid_series),
				)
			)

		key = (row.document_type, row.naming_series)
		if key in seen:
			frappe.throw(
				_("Duplicate rule for {0} and series {1}.").format(
					frappe.bold(row.document_type),
					frappe.bold(row.naming_series),
				)
			)
		seen.add(key)


def get_doctype_naming_series(doctype):
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} does not exist.").format(frappe.bold(doctype)))

	meta = frappe.get_meta(doctype)
	field = meta.get_field(SERIES_FIELD)
	if not field:
		return []

	return [option.strip() for option in cstr(field.options).splitlines() if option.strip()]


def _validate_unique_user(doc):
	if not doc.user:
		return

	duplicates = frappe.get_all(
		SETTINGS_DOCTYPE,
		filters={"user": doc.user, "name": ["!=", doc.name]},
		pluck="name",
		limit=1,
	)
	if duplicates:
		frappe.throw(_("User Naming Series already exists for user {0}.").format(frappe.bold(doc.user)))


def _should_enforce(doc):
	if not doc or doc.doctype in {SETTINGS_DOCTYPE, DETAIL_DOCTYPE}:
		return False
	if getattr(doc.meta, "istable", False) or not doc.is_new():
		return False
	if not frappe.session or not frappe.session.user or frappe.session.user == "Guest":
		return False
	return bool(doc.meta.get_field(SERIES_FIELD))


def _settings_tables_exist():
	try:
		return frappe.db.table_exists(SETTINGS_DOCTYPE) and frappe.db.table_exists(DETAIL_DOCTYPE)
	except Exception:
		return False
