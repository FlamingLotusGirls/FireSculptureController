/* Local touchscreen editor. Drafts never reach a field until Done. */
(function($){
	'use strict';
	if (!isTouchDisplay) return;

	var active = null;
	var physicalKeyboard = false;
	var statusRequest = null;

	function checkPhysicalKeyboard(){
		if (statusRequest) return statusRequest;
		statusRequest = $.ajax({url: '/jsGui/kiosk-input.json', dataType: 'json', cache: false, timeout: 500})
			.done(function(status){
				var age = Date.now() - status.updatedAt;
				physicalKeyboard = status.keyboardConnected === true && age >= -1000 && age < 5000;
			}).fail(function(){ physicalKeyboard = false; })
			.always(function(){ statusRequest = null; });
		return statusRequest;
	}
	var normalRows = [
		['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Backspace'],
		['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'],
		['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'"],
		['Shift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/']
	];
	var shiftedRows = [
		['~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', 'Backspace'],
		['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{', '}', '|'],
		['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':', '"'],
		['Shift', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>', '?']
	];

	function editable(element){
		return !element.disabled && !element.readOnly &&
			!$(element).closest('.softKeyboard').length &&
			(element.tagName == 'TEXTAREA' ||
			 /^(text|search|tel|url|email|password|number)$/.test(element.type));
	}

	function fieldName(element){
		var label = $('label').filter(function(){ return this.htmlFor === element.id; }).first().text();
		return element.getAttribute('aria-label') || label ||
			$(document.getElementById(element.id + '_description')).text() || 'value';
	}

	function openKeyboard(element){
		if (active || !editable(element)) return;
		var source = $(element);
		var integer = element.getAttribute('inputmode') == 'numeric';
		var numeric = integer || element.type == 'number' || element.getAttribute('inputmode') == 'decimal';
		var multiline = element.tagName == 'TEXTAREA';
		var title = 'Edit ' + fieldName(element).trim();
		var panel = $('<div class="softKeyboard">').appendTo('body');
		var preview = $(multiline ? '<textarea rows="2">' : '<input>')
			.addClass('softKeyboardPreview').attr({
				'aria-label': title, inputmode: 'none', autocomplete: 'off', spellcheck: 'false'
			}).val(source.val()).appendTo(panel);
		if (element.type == 'password') preview.attr('type', 'password');
		if (element.maxLength >= 0) preview.attr('maxlength', element.maxLength);
		var error = $('<div class="softKeyboardError" role="alert">').appendTo(panel);
		var keys = $('<div class="softKeyboardKeys">').appendTo(panel);
		var shifted = false;
		var closed = false;
		active = panel;

		function replaceSelection(text, backspace){
			var input = preview[0], value = preview.val();
			var start = input.selectionStart, end = input.selectionEnd;
			if (backspace && start == end && start > 0){
				// Do not split a surrogate pair when deleting pasted Unicode text.
				start -= /[\uDC00-\uDFFF]/.test(value.charAt(start - 1)) && start > 1 ? 2 : 1;
			}
			var next = value.slice(0, start) + text + value.slice(end);
			if (element.maxLength >= 0 && next.length > element.maxLength) return;
			preview.val(next);
			input.setSelectionRange(start + text.length, start + text.length);
			error.text('');
		}

		function finish(){
			if (closed) return;
			if (!document.documentElement.contains(element)){
				panel.dialog('close');
				return;
			}
			var value = preview.val();
			if (numeric){
				var valid = integer ? /^-?\d+$/.test(value) : value.trim() !== '' && isFinite(Number(value));
				if (!valid){
					error.text(integer ? 'Enter a whole number.' : 'Enter a number.');
					return;
				}
				var min = source.attr(source.hasClass('knob') ? 'data-min' : 'min');
				var max = source.attr(source.hasClass('knob') ? 'data-max' : 'max');
				if (min != null && min !== '' && Number(value) < Number(min) ||
					max != null && max !== '' && Number(value) > Number(max)){
					error.text('Value is outside the allowed range' +
						(min != null ? ' (min ' + min + ')' : '') + (max != null ? ' (max ' + max + ')' : '') + '.');
					return;
				}
			}
			// Existing field handlers retain their normal behavior. Editing a
			// dialog field does not press Update, and editing a command does not Send.
			if (source.val() !== value){
				source.val(value).trigger('input').trigger('change');
			}
			panel.dialog('close');
		}

		function press(key){
			var input = preview[0];
			if (key == 'Done'){ finish(); return; }
			if (key == 'Cancel'){ panel.dialog('close'); return; }
			preview.focus();
			if (key == 'Shift'){
				shifted = !shifted;
				renderKeys();
			} else if (key == 'Left' || key == 'Right'){
				var position = key == 'Left' ? Math.max(0, input.selectionStart - 1) : Math.min(preview.val().length, input.selectionEnd + 1);
				input.setSelectionRange(position, position);
			} else if (key == 'Clear'){
				input.select();
				replaceSelection('');
			} else {
				replaceSelection(key == 'Backspace' ? '' : key == 'Space' ? ' ' : key == 'Enter' ? '\n' : key, key == 'Backspace');
			}
		}

		function renderKeys(){
			keys.empty();
			var rows = numeric ? [
				['7', '8', '9', 'Backspace'], ['4', '5', '6', '-'],
				['1', '2', '3', 'Clear'], ['0', 'Left', 'Right'].concat(integer ? [] : ['.']),
				['Cancel', 'Done']
			] : (shifted ? shiftedRows : normalRows).concat([
				['Left', 'Right', 'Space', 'Clear'].concat(multiline ? ['Enter'] : []).concat(['Cancel', 'Done'])
			]);
			$.each(rows, function(_, row){
				var line = $('<div class="softKeyboardRow">').appendTo(keys);
				$.each(row, function(_, key){
					var button = $('<button type="button">').text(key).attr('data-key', key).appendTo(line);
					if (key == 'Space') button.addClass('softKeyboardSpace');
					if (key == 'Backspace') button.addClass('softKeyboardWide').text('⌫').attr('aria-label', 'Backspace');
					if (key == 'Left' || key == 'Right') button.text(key == 'Left' ? '←' : '→').attr('aria-label', key);
					if (key == 'Shift') button.attr('aria-pressed', String(shifted));
					if (key == 'Done') button.addClass('softKeyboardDone');
				});
			});
		}
		// Keep the preview's caret/selection when a key is touched or clicked.
		keys.on('mousedown', 'button', function(event){ event.preventDefault(); });
		keys.on('click', 'button', function(){ press(this.getAttribute('data-key')); });
		preview.on('keydown', function(event){
			if (event.keyCode == 13 && !multiline){ event.preventDefault(); finish(); }
		});
		renderKeys();
		panel.dialog({
			title: title,
			dialogClass: 'softKeyboardDialog',
			modal: true, draggable: false, resizable: false,
			width: Math.min(numeric ? 420 : 780, $(window).width() - 16),
			maxHeight: $(window).height() - 16,
			close: function(){
				closed = true;
				active = null;
				$(this).dialog('destroy').remove();
			},
			open: function(){ preview.focus(); preview[0].select(); }
		});
	}

	// Delegate so fields rebuilt by SSE and fields created inside dialogs work.
	// Opening on a tap, rather than focus, also permits normal hardware typing.
	$(document).on('click.softKeyboard', 'input, textarea', function(){
		var element = this;
		if (active || !editable(element)) return;
		checkPhysicalKeyboard().always(function(){
			if (!physicalKeyboard && document.activeElement === element) openKeyboard(element);
		});
	});
}(jQuery));
