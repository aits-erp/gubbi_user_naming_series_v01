(function () {
	let rules = null;

	function get_rules() {
		if (rules) {
			return Promise.resolve(rules);
		}

		if (frappe.boot && frappe.boot.user_naming_series_rules) {
			rules = frappe.boot.user_naming_series_rules;
			return Promise.resolve(rules);
		}

		return frappe.call({
			method: "user_naming_series.user_series.get_user_series_map",
		}).then((response) => {
			rules = response.message || {};
			return rules;
		});
	}

	function apply_rules(frm) {
		if (!frm || !frm.doc || !frm.fields_dict || !frm.fields_dict.naming_series) {
			return;
		}

		get_rules().then((user_rules) => {
			const allowed = user_rules[frm.doctype];
			if (!allowed || !allowed.length || !frm.fields_dict.naming_series) {
				return;
			}

			const options = allowed.join("\n");
			frm.set_df_property("naming_series", "options", options);

			if (!allowed.includes(frm.doc.naming_series)) {
				frm.set_value("naming_series", allowed[0]);
			}
		});
	}

	function apply_to_current_form() {
		if (window.cur_frm) {
			apply_rules(window.cur_frm);
		}
	}

	function apply_list_rules() {
		if (!frappe.get_route) {
			return;
		}

		const route = frappe.get_route();
		if (!route || route[0] !== "List" || !route[1]) {
			return;
		}

		const doctype = route[1];
		get_rules().then((user_rules) => {
			const allowed = user_rules[doctype];
			if (!allowed || !allowed.length) {
				return;
			}

			frappe.route_options = frappe.route_options || {};
			frappe.route_options.naming_series = ["in", allowed];

			if (!window.cur_list || window.cur_list.doctype !== doctype || !window.cur_list.filter_area) {
				return;
			}

			const key = allowed.join("\n");
			if (window.cur_list.user_naming_series_filter === key) {
				return;
			}

			window.cur_list.user_naming_series_filter = key;
			window.cur_list.filter_area.add(doctype, "naming_series", "in", allowed);
		});
	}

	$(document).on("form-refresh", function (_event, frm) {
		apply_rules(frm);
	});

	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			setTimeout(apply_to_current_form, 300);
			setTimeout(apply_list_rules, 300);
		});
	}
})();
