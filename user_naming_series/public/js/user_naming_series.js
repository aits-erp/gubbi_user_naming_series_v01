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

	$(document).on("form-refresh", function (_event, frm) {
		apply_rules(frm);
	});

	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			setTimeout(apply_to_current_form, 300);
		});
	}
})();
