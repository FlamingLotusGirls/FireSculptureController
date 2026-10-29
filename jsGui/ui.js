var settings = {
	'serverUrl' : '/'
};
var allSculptureData = false;
var currentView = {'activeTab' : false, 'activeModule' : false, activeSections : {}, sculptureIsLoaded:false}
var serverSentEventStream = false;
var stateRefresh = {pending: false, timer: null, inFlight: false, pointers: {}};
var serialPortOptions = [];
var connectionStatusInFlight = false;
var lastConnectionStatus = '';
var connectionErrors = {};
var isTouchDisplay = /(?:^|[?&])display=touch(?:&|$)/.test(window.location.search);
if (isTouchDisplay){
	document.documentElement.classList.add('touch-display');
}


function convertRGBTupleToRGBString(tuple) {
	return "rgb(" + tuple[0] + "," + tuple[1] + "," + tuple[2] + ")";
};


function handleDataStreamEvent(data){
	// State notifications must not rebuild controls during live operation.
	// Use the header refresh button to pick up edits from another browser.
	if (data.log){
		$.each(data.log, function(logIndex, logItem){
			$('#logDiv').prepend(logItem + '<br>');
		});
	}
	if (data.sculptures){
		allSculptureData.sculptures = $.extend(true, allSculptureData.sculptures, data.sculptures);
		updateStatusDisplay();
	}
	if (data.outputChanged){
		$.each(data.outputChanged, function(index, outputChangeMessage){
			$.each(outputChangeMessage.data, function(index, pointData){
				if (outputChangeMessage.moduleId == 'leds') {
					var element = $('#' +
							outputChangeMessage.moduleId +
							'_' +
							pointData[0][0] +
							'_' + pointData[0][1] +
							'_label')[0];
					if (element) element.style.background =
						convertRGBTupleToRGBString(pointData[1]);

				} else {
					var element = $('#' +
							outputChangeMessage.moduleId +
							'_' +
							pointData[0][0] +
							'_' + pointData[0][1]);
					element.prop('checked', pointData[1]);

				}
			});
		});
		$('.outputViewRow').buttonset('refresh');
	}

}

function typesAreCompatible(type1, type2){
	result = false;
	if ((type1 == type2) || (type1 == 'pulse' && type2 == 'toggle') ||  (type2 == 'pulse' && type1 == 'toggle')){
		result = true;
	}
	return result;

}

function showRebindDialog(moduleId, patternInstanceId, inputChannelId){
	selectData = {'id' : 'inputSelector', 'onChange' : 'onChange = "showInputParamsForm()"', 'options' : [{'description' : 'Select Input', 'value' : 'none'}]};
	if (patternInstanceId){
		inputChannelType = allSculptureData.modules[moduleId].patterns[patternInstanceId].inputs[inputChannelId].type;
	}
	else {
		inputChannelType = allSculptureData.modules[moduleId].inputs[inputChannelId].type;
	}
	$.each(allSculptureData.availableInputTypes[inputChannelType], function(subType, typeData){
		selectData.options.push({'description' : "(New)" + typeData.longDescription, 'value' : JSON.stringify(['new', inputChannelType, subType])});
	});
	if (inputChannelType != 'multi'){
		$.each(allSculptureData.inputs, function(inputInstanceId, inputData){
			if ($.inArray(parseInt(inputInstanceId), allSculptureData.globalInputs) > -1){
				$.each(inputData.outParams, function(outputIndex, outputData){
					if (typesAreCompatible(outputData.type, inputChannelType) ){
						selectData.options.push({'description' : "(Running)" + inputData.shortDescription + ' ' + outputData.description, 'value' : JSON.stringify(['running', inputInstanceId , outputIndex])});
					}
				});
			}
		});
	}
	$('#dialog').append($('#selectTemplate').render(selectData));
	$('#dialog').append('<div id="dialogInputs"></div>');
	$('#dialog').dialog({
		title: 'Change input',
		autoOpen: true,
		height: isTouchDisplay ? Math.min(400, $(window).height() - 24) : 300,
		width: isTouchDisplay ? Math.min(420, $(window).width() - 24) : 350,
		dialogClass: isTouchDisplay ? 'inputBindingDialog' : '',
		draggable: !isTouchDisplay,
		resizable: !isTouchDisplay,
		modal: true,
		buttons: {
			"Update": function() {
				if (doNewInputBinding(moduleId, patternInstanceId, inputChannelId) !== false){
					$(this).dialog("close");
				}
			},
			"Cancel": function() {
				$(this).dialog("close");
			}
		},
		close: function(event, ui) {
			$(this).empty().dialog('destroy');
		}
	});
	initInputSelector();
}
function showGlobalInputDialog(){
	selectData = {'id' : 'inputSelector', 'onChange' : 'onChange = "showInputParamsForm()"', 'options' : [{'description' : 'Select Input', 'value' : 'none'}]};
	$.each(allSculptureData.availableGlobalInputs, function(typeIndex, typeData){
		selectData.options.push({'description' : allSculptureData.availableInputTypes[typeData[0]][typeData[1]].longDescription, 'value' : JSON.stringify(['new', typeData[0], typeData[1]])});
	});
	$('#dialog').append($('#selectTemplate').render(selectData));
	$('#dialog').append('<div id="dialogInputs"></div>');
	$('#dialog').dialog({
		title: 'Add input',
		autoOpen: true,
		height: isTouchDisplay ? Math.min(400, $(window).height() - 24) : 300,
		width: isTouchDisplay ? Math.min(420, $(window).width() - 24) : 350,
		dialogClass: isTouchDisplay ? 'inputBindingDialog' : '',
		draggable: !isTouchDisplay,
		resizable: !isTouchDisplay,
		modal: true,
		buttons: {
			"Update": function() {
				if (doNewInputBinding('main') !== false){
					$(this).dialog("close");
				}
			},
			"Cancel": function() {
				$(this).dialog("close");
			}
		},
		close: function(event, ui) {
			$(this).empty().dialog('destroy');
		}
	});
	initInputSelector();
}

function initInputSelector(){
	var select = $('#inputSelector');
	var updateButton = $('#dialog').dialog('widget').find('.ui-dialog-buttonpane button').first();
	function updateSelection(){
		updateButton.button('option', 'disabled', !select.val() || select.val() == 'none');
	}
	select.on('change.inputSelector', updateSelection);
	updateSelection();
	if (!isTouchDisplay) return;

	// Cog's DRM platform cannot show native select popups. Keep the select as
	// the form value and render its choices inside the existing modal instead.
	select.hide().attr('aria-hidden', 'true');
	var choices = $('<div id="inputSelectorChoices" class="inputSelectorChoices" role="group" aria-label="Input types">')
		.insertAfter(select);
	select.find('option').each(function(){
		var option = this;
		if (option.value == 'none') return;
		$('<button type="button" class="inputSelectorChoice">')
			.text(option.text).prop('disabled', option.disabled)
			.attr('aria-pressed', String(option.selected))
			.appendTo(choices).button().click(function(){
				choices.find('button').attr('aria-pressed', 'false');
				$(this).attr('aria-pressed', 'true');
				select.val(option.value).trigger('change');
			});
	});
}

function doNewInputBinding(moduleId, patternInstanceId, inputChannelId){
	var selected = $('#inputSelector').val();
	if (!selected || selected == 'none') return false;
	var values = JSON.parse(selected);
	if (values[0] == 'running'){
		if (patternInstanceId){
			doCommand(['reassignPatternInput', moduleId, patternInstanceId, inputChannelId, parseInt(values[1]), parseInt(values[2])])
		}
		else {
			doCommand(['reassignModuleInput', moduleId, inputChannelId, parseInt(values[1]), parseInt(values[2])])
		}
	}
	else if (values[0] == 'new'){
		params = {'type' : values[1], 'subType' : values[2], 'inParams' : []}
		inputTypeData = allSculptureData.availableInputTypes[values[1]][values[2]];
		if (inputTypeData.setupParamsNeeded){
			$.each(inputTypeData.setupParamsNeeded, function (paramIndex, paramData){
				formInputId = '#inputDefinitionMainParam' + paramData[2];
				switch (paramData[0]){
					case 'text':
						params[paramData[2]] = $(formInputId).val();
					break;
					case 'textList':
						params[paramData[2]] = $(formInputId).val().split(' ');
					break;
					case 'int':
						params[paramData[2]] = parseInt($(formInputId).val());
					break;
					case 'bool':
						params[paramData[2]] = $(formInputId).is(":checked");
					break;
				}
			});
		}
		if (inputTypeData.inParams){
			$.each(inputTypeData.inParams, function (inputIndex, inputData){
				configData = {}
				if (inputData.setupParamsNeeded){
					paramsData = inputData.setupParamsNeeded;
				}
				else if (inputData.type == 'value'){
					paramsData = [['int', 'Minimum', 'min'], ['int', 'Maximum', 'max']]
				}
				else {
					paramsData = []
				}
				$.each(paramsData, function (paramIndex, paramData){
					formInputId = '#inputDefinitionInputParam' + inputIndex + paramData[2];
					data = false;
					switch (paramData[0]){
						case 'text':
							data = $(formInputId).val();
						break;
						case 'int':
							data = parseInt($(formInputId).val());
						break;
						case 'bool':
							data = $(formInputId).is(":checked");
						break;
					}
					configData[paramData[2]] = data;
				});
				params.inParams.push(configData)
			});
		}
		params = $.extend(true, inputTypeData, params);
		delete params.setupParamsNeeded;
		if (moduleId == 'main'){
			doCommand(['addGlobalInput', params]);
		}
		else {
			if (patternInstanceId){
				doCommand(['reassignPatternInputToNew', moduleId, patternInstanceId, inputChannelId, params]);
			}
			else {
				doCommand(['reassignModuleInputToNew', moduleId, inputChannelId, params]);
			}
		}
	}
}

function showInputParamsForm(){
	var selected = $('#inputSelector').val();
	$('#dialogInputs').empty();
	if (!selected || selected == 'none') return;
	var values = JSON.parse(selected);
	formFields = [];
	if (values[0] == 'new'){
		inputTypeData = allSculptureData.availableInputTypes[values[1]][values[2]];
		if (inputTypeData.setupParamsNeeded){
			$.each(inputTypeData.setupParamsNeeded, function (paramIndex, paramData){
				fieldData = {"id" : "inputDefinitionMainParam" + paramData[2], "label" : paramData[1]}
				fieldData.inputMode = paramData[0] == 'int' ? 'numeric' : 'text';
				if (paramData[0] == 'text' || paramData[0] == 'textList' || paramData[0] == 'int'){
					fieldData['input'] = true;
					if (inputTypeData[paramData[2]] != undefined){
						fieldData['value'] = inputTypeData[paramData[2]];
					}
				}
				else if (paramData[0] == 'bool'){
					fieldData['checkbox'] = true;
				}
				formFields.push(fieldData);
			});
		}
		if (inputTypeData.inParams){
			$.each(inputTypeData.inParams, function (inputIndex, inputData){
				if (inputData.setupParamsNeeded){
					paramsData = inputData.setupParamsNeeded;
				}
				else if (inputData.type == 'value'){
					paramsData = [['int', 'Minimum', 'min'], ['int', 'Maximum', 'max']]
				}
				else {
					paramsData = []
				}
				$.each(paramsData, function (paramIndex, paramData){
					fieldData = {"id" : "inputDefinitionInputParam" + inputIndex + paramData[2], "label" : inputData.description + ':' + paramData[1]}
					fieldData.inputMode = paramData[0] == 'int' ? 'numeric' : 'text';
					if (paramData[2] in inputData){
						paramDefault = inputData[paramData[2]];
						if (typeof(paramDefault) == 'number'){
							fieldData['value'] = paramDefault.toString();
						}
						else if (typeof(paramDefault) == 'boolean'){
							if (paramDefault){
								fieldData['value'] = true;
							}
						}
						else {
							fieldData['value'] = paramDefault;
						}
					}
					if (paramData[0] == 'text' || paramData[0] == 'int'){
						fieldData['input'] = true;
					}
					else if (paramData[0] == 'bool'){
						fieldData['checkbox'] = true;
					}
					formFields.push(fieldData);
				});
			});
		}
	}
	$('#dialogInputs').html($('#formFieldsTemplate').render({'fields' : formFields}));
}


function doInit(){
	var pressEvents = window.PointerEvent ? 'pointerdown' : 'mousedown touchstart';
	var releaseEvents = window.PointerEvent ? 'pointerup pointercancel' : 'mouseup touchend touchcancel';
	$(document).on(pressEvents, function(event){
		stateRefresh.pointers[event.originalEvent.pointerId || 'pointer'] = true;
	}).on(releaseEvents, function(event){
		delete stateRefresh.pointers[event.originalEvent.pointerId || 'pointer'];
		scheduleStateRefresh();
	}).on('focusout dialogclose', function(){
		// Let the blur/close handler finish before deciding whether redraw is safe.
		setTimeout(scheduleStateRefresh, 0);
	});
	$(window).on('blur', function(){
		stateRefresh.pointers = {};
		scheduleStateRefresh();
	});
	reloadData();
	serverSentEventStream = new EventSource('/dataStream');
	// Reconnecting the stream must not interrupt trigger controls either.
	serverSentEventStream.onopen = refreshConnectionStatus;
	serverSentEventStream.onmessage = function (event) {
		handleDataStreamEvent(JSON.parse(event.data));
	};
	serverSentEventStream.onerror = function () {
		$('#logDiv').prepend('<span style="font-weight:bold; font-color:FFCD4D">Connection error</span><br>');
	};
	setInterval(refreshConnectionStatus, 2000);

}

function setCurrentModuleView(moduleId){
	currentView.activeModule = moduleId;
	var heading = $('#' + currentView.activeSections[moduleId] + '_heading');
	var moduleData = allSculptureData.modules && allSculptureData.modules[moduleId];
	if (heading.length){
		heading.click();
	}
	else if (moduleData && moduleData.inputs){
		hideAllInputs();
		$('#inputs').detach().appendTo('#' + moduleId + '_inputs');
		$.each(moduleData.inputs, function(inputChannelId, inputData){
			showInput(moduleId + '_mainInput', inputData, inputChannelId);
		});
	}
	else {
		delete currentView.activeSections[moduleId];
	}
}

function reloadData(){
	stateRefresh.pending = true;
	scheduleStateRefresh();
}

function stateRefreshBlocked(){
	return !$.isEmptyObject(stateRefresh.pointers)
		|| $('#dialog').is('.ui-dialog-content:visible')
		|| $('.softKeyboard').is(':visible')
		|| $(document.activeElement).is('textarea, input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit])');
}

function scheduleStateRefresh(){
	if (!stateRefresh.pending || stateRefresh.timer || stateRefresh.inFlight || stateRefreshBlocked()) return;
	stateRefresh.timer = setTimeout(fetchState, 100);
}

function fetchState(){
	stateRefresh.timer = null;
	if (stateRefreshBlocked()) return;
	stateRefresh.pending = false;
	stateRefresh.inFlight = true;
	$.ajax(settings.serverUrl + 'getData', {
		dataType: 'json',
		cache: false
	}).done(function(result) {
		if (stateRefreshBlocked()){
			stateRefresh.pending = true;
			return;
		}
		if (allSculptureData && allSculptureData.sculptureId != result.sculptureId){
			currentView = {activeTab: false, activeModule: false, activeSections: {}, sculptureIsLoaded: false};
		}
		else {
			currentView.sculptureIsLoaded = !!(allSculptureData && allSculptureData.sculptureId);
		}
		allSculptureData = result;
		buildAll();
	}).fail(function(){
		$('<div>').text('Could not refresh controller state.').prependTo('#logDiv');
	}).always(function(){
		stateRefresh.inFlight = false;
		scheduleStateRefresh();
	});
}

function buildAll(){
	if (allSculptureData.sculptureId){
		if (currentView.sculptureIsLoaded){
			$('#logStorage').html($('#logDiv').html());
		}
		$('#mainDiv').html('');
		$('#mainDiv').append($('#sculptureControllerTemplate').render(makeSculptureControllerTemplateData()));
		if (currentView.sculptureIsLoaded){
			$('#logDiv').html($('#logStorage').html());
		}
		$.each( allSculptureData.inputs, function( inputInstanceId, inputData ) {
			buildInputControls(inputInstanceId, inputData);
		});
		$.each( allSculptureData.modules, function( moduleId, moduleData ) {
			switch(moduleData.moduleType){
				case 'Leds':
					buildLEDsModule(moduleData);
					break;
				case 'Poofer':
					buildPooferModule(moduleData);
					break;
				case 'InputOnly':
					buildInputOnlyModule(moduleData);
					break;
			}
		});
		$(".accordion").each(function(){
			$(this).accordion({
				collapsible: true,
				active: false,
				heightStyle: $(this).hasClass('patternList') ? 'content' : 'auto'
			});
		});
		if (currentView.activeModule){
			$('#sculptureControl').tabs({ active : $("#sculptureControl>div").index($("#" + currentView.activeModule + '_module')) });
		}
		else{
			$('#sculptureControl').tabs();
		}
		$('#addGlobalInputButton').button().click(function(e){
			showGlobalInputDialog()
		});
		$('.globalInputButton').button().click(function(){
			doCommand(['removeGlobalInput', parseInt(this.id.split('_')[1])]);
		});
		$('.removePatternButton').button().click(function(){
			$(this).button('disable');
			var parts = this.id.split('_');
			doCommand(['removePattern', parts[0], parts[1]]);
		});
		$('#refreshStateButton').button().click(reloadData);
		$('#safeButtonDiv').buttonset();
		$('#safeModeOn').click(function(e){
			doCommand(['setSafeMode', true]);
		});
		$('#safeModeOff').click(function(e){
			doCommand(['setSafeMode', false]);
		});
		$('#sendDirectCommandButton').button().click(function(){
			doCommand(JSON.parse($('#sendDirectCommandInput').val()));
			$('#sendDirectCommandInput').val('')
		});
		$('.serialPortSelect').change(function(){
			var adaptorId = $(this).closest('.serialAdaptorRow').attr('data-adaptor-id');
			if (this.value) doCommand(['updateSerialConnection', adaptorId, {ports: JSON.parse(this.value)}]);
		});
		$('.serialAdaptorRow input').change(function(){
			var adaptorId = $(this).closest('.serialAdaptorRow').attr('data-adaptor-id');
			var baudrate = Number(this.value);
			if (baudrate > 0 && baudrate % 1 == 0){
				doCommand(['updateSerialConnection', adaptorId, {baudrate: baudrate}]);
			}
			else { reloadData(); }
		});
		$('#refreshSerialPortsButton').button().click(refreshSerialPorts);
		populateSerialPorts();
		refreshSerialPorts();
		refreshConnectionStatus();
		if (currentView.activeModule){
			setCurrentModuleView(currentView.activeModule);
		}
	}
	else {
		data = {"sculptures" : []};
		$.each(allSculptureData['sculptures'], function(sculptureId, sculptureData) {
			data.sculptures.push({"sculptureId" : sculptureId, "sculptureName" : sculptureData.sculptureName});
		});
		$('#mainDiv').html($('#sculptureChooserTemplate').render(data));
		$('.sculptureChoice').button().click(function(){
			doCommand(['loadSculpture', this.id.split('_')[0]]);
		});
	}
	$('#mainDiv').css('height', $(window).height() * 0.88 + 'px');
}


function refreshSerialPorts(){
	$.ajax(settings.serverUrl + 'serialPorts', {dataType: 'json', cache: false}).done(function(result){
		serialPortOptions = result.ports;
		$('#serialPortDiscoveryStatus').text(result.error || (result.ports.length ? '' : 'No serial adapters detected.'));
		populateSerialPorts();
	}).fail(function(){
		$('#serialPortDiscoveryStatus').text('Could not refresh serial adapters.');
	});
}

function populateSerialPorts(){
	if (!allSculptureData || !allSculptureData.adaptors) return;
	$('.serialPortTouchChoices').remove();
	$('.serialPortSelect').each(function(){
		var select = $(this);
		var adaptorId = select.closest('.serialAdaptorRow').attr('data-adaptor-id');
		var adaptor = allSculptureData.adaptors[adaptorId];
		var selected = JSON.stringify(adaptor.ports);
		select.empty();
		$('<option>').val('').text('Select USB adapter').appendTo(select);
		var found = false;
		$.each(serialPortOptions, function(index, port){
			var matches = $.inArray(port.port, adaptor.ports) >= 0 || $.inArray(port.device, adaptor.ports) >= 0;
			if (adaptor.identity && port.identity){
				matches = matches || (adaptor.identity.serialNumber == port.identity.serialNumber
					&& adaptor.identity.vid == port.identity.vid && adaptor.identity.pid == port.identity.pid
					&& adaptor.identity.interface == port.identity.interface);
			}
			var value = JSON.stringify([port.port]);
			$('<option>').val(value).text(port.label).appendTo(select);
			if (matches){ selected = value; found = true; }
		});
		if (!found && adaptor.ports.length){
			$('<option>').val(selected).text('Saved device (not detected): ' + adaptor.ports.join(' ')).appendTo(select);
		}
		select.val(selected);
		if (isTouchDisplay){
			// Cog's DRM backend cannot display native select popups.
			select.hide().attr('aria-hidden', 'true');
			var button = $('<button type="button" class="serialPortTouchChoices">')
				.text(select.find('option:selected').text()).insertAfter(select).button();
			button.click(function(){
				var choices = $('<div class="inputSelectorChoices">');
				select.find('option').each(function(){
					var option = this;
					if (!option.value) return;
					$('<button type="button" class="inputSelectorChoice">').text(option.text)
						.appendTo(choices).button().click(function(){
							select.val(option.value).trigger('change');
							button.text(option.text);
							$('#dialog').dialog('close');
						});
				});
				$('#dialog').empty().append(choices).dialog({title: 'USB adapter', modal: true,
					width: Math.min(620, $(window).width() - 24),
					maxHeight: $(window).height() - 24,
					buttons: {Cancel: function(){ $(this).dialog('close'); }},
					close: function(){ $(this).empty().dialog('destroy'); }});
			});
		}
	});
}

function refreshConnectionStatus(){
	if (connectionStatusInFlight || !$('#connectionStatus').length) return;
	connectionStatusInFlight = true;
	$.ajax(settings.serverUrl + 'connectionStatus', {dataType: 'json', cache: false}).done(function(result){
		var signature = JSON.stringify(result);
		if (signature == lastConnectionStatus && $('#connectionStatus').children().length) return;
		lastConnectionStatus = signature;
		// Keep the safety indicator current without replacing any controls.
		allSculptureData.safeMode = result.safeMode;
		$('#safeModeOn').prop('checked', result.safeMode);
		$('#safeModeOff').prop('checked', !result.safeMode);
		$('#safeButtonDiv').buttonset('refresh');
		var panel = $('#connectionStatus').empty().removeClass('connectionWarning');
		$.each(result.connections, function(index, connection){
			var text;
			var missing = connection.modules.length && !connection.connected;
			if (!connection.modules.length){ text = 'Unused by this sculpture'; }
			else if (!connection.connected){ text = 'Disconnected — output blocked'; }
			else if (connection.deliveryPending){ text = 'Output pending'; }
			else { text = 'Port connected'; }
			$('#' + connection.adaptorId + 'Connection').text(text);
			if (!connection.modules.length) return;
			var row = $('<div>').appendTo(panel);
			$('<strong>').text(connection.adaptorId + ': ' + text).appendTo(row);
			if (missing){
				var detail = connection.lastError || connection.writerError || connection.ports.join(' ');
				row.attr('title', detail);
				if (connectionErrors[connection.adaptorId] != detail){
					$('<div>').text(connection.adaptorId + ': ' + detail).prependTo('#logDiv');
					connectionErrors[connection.adaptorId] = detail;
				}
				if (!result.safeMode){ panel.addClass('connectionWarning'); }
			}
			else {
				delete connectionErrors[connection.adaptorId];
				if (connection.writerError) row.attr('title', connection.writerError);
			}
		});
		$('#settingsStatus').text(result.settingsError || '').toggleClass('connectionWarning', !!result.settingsError);
	}).fail(function(){
		$('#connectionStatus').text('Hardware status unavailable — cannot reach controller.').addClass('connectionWarning');
		lastConnectionStatus = '';
	}).always(function(){ connectionStatusInFlight = false; });
}

function makeSculptureControllerTemplateData(){
	data = {"sculptureName" : allSculptureData.sculptureName, "modules" : [], "inputs" : [], "globalInputs" : [], "serialAdaptors" : []};
	$.each( allSculptureData.inputs, function( inputInstanceId, inputData ) {
		templateInputData = {"inputInstanceId" : inputInstanceId, "inParams" : [], "outParams" : []}
		$.each(inputData.inParams, function(inputIndex){
			templateInputData.inParams.push({'inputIndex' : inputIndex, 'inputInstanceId' : inputInstanceId});
		});
		$.each(inputData.outParams, function(outputIndex){
			templateInputData.outParams.push({'outputIndex' : outputIndex, 'inputInstanceId' : inputInstanceId});
		});
		data.inputs.push(templateInputData);
	});
	$.each( allSculptureData.modules, function( moduleId, moduleData ) {
		data.modules.push({"moduleId" : moduleId, "name" : moduleData.name});
	});
	$.each(allSculptureData.globalInputs, function (index, inputInstanceId){
		data.globalInputs.push({'value' : inputInstanceId.toString(), 'name' : allSculptureData.inputs[inputInstanceId].shortDescription})
	});
	$.each(allSculptureData.adaptors, function(adaptorId, adaptorData){
		if (adaptorData.type=="serial"){
			data.serialAdaptors.push({'adaptorId' : adaptorId, 'ports' : adaptorData.ports.join(' '), 'baudrate' : adaptorData.baudrate});
		}
	});
	if (allSculptureData.safeMode){
		data['safeMode'] = true;
	}
	return data;
}

function buildLEDsModule(moduleData){
	moduleId = moduleData.moduleId
	// At first, parse the given 'moduleData' object and convert it to
	// local data format.
	templateModuleData = {
		"moduleId" : moduleId,
		"name" : moduleData.name,
		"availablePatternNames" : [],
		"patterns" : [],
		"inputs" : [],
		"rows" : []};
	$.each( moduleData.availablePatternNames, function( patternIndex, patternName ) {
		templateModuleData.availablePatternNames.push({"name" : patternName});
	});
	$.each( moduleData.patterns, function( patternInstanceId, patternData ) {
		templatePatternData = {
			"patternName" : patternData.name,
			"patternInstanceId" : patternInstanceId,
			"rowSettings" : [],
			"moduleId" : moduleId};
		$.each(patternData.rowSettings, function(rowIndex, rowSetting){
			rowData = {
				"moduleId" : moduleId,
				"patternInstanceId" : patternInstanceId,
				"rowIndex" : rowIndex};
			if (rowSetting) rowData['enabled'] = true;
			templatePatternData.rowSettings.push(rowData);
		});
		templateModuleData.patterns.push(templatePatternData);
	});
	$.each( moduleData.protocol.mapping, function( rowIndex, rowData ) {
		templateRowData = {
			"rowIndex" : rowIndex,
			"moduleId" : moduleId,
			"cols" : []};
		$.each( rowData, function( colIndex, colData ) {
			templateRowData.cols.push({
				"rowIndex" : rowIndex,
				"moduleId" : moduleId,
				"colIndex" : colIndex});
			if (moduleData.enabledStatus[rowIndex][colIndex]){
				templateRowData.cols[colIndex]['enabled'] = true;
			}
		});
		templateModuleData.rows.push(templateRowData);
	});

	// Then, render the data.
	$('#' + moduleId + '_module').html(
		$('#ledModuleTemplate').render(templateModuleData));
	initPatternChooser(moduleId);
	$('#' + moduleId + '_removePatternButton').button().click(function(e){
		patternId = $('#' + moduleId + '_patternSelection').val();
		if (patternId && patternId != 'none'){
			doCommand(['removePattern', moduleId, patternId]);
		}
	});
	$.each( moduleData.protocol.mapping, function( rowIndex, rowData ) {
		$('#' + moduleId + '_outputView_row' + rowIndex).buttonset();
		$('#' + moduleId + '_enableView_row' + rowIndex).buttonset();
	});
	$('#' + moduleId + '_module .toggleRowButton').button().click(function(){
		parts = this.id.split('_');
		doCommand(['toggleRowSelection',
			   parts[0], parts[1], parseInt(parts[2])]);
		$('label[for="' + this.id + '"] > .ui-button-text').html('Row ' + parts[2] + ($('#' + this.id).is(":checked")?' Enabled':' Disabled'));
	});
	$('#' + moduleId + '_module .ledDisplay').click(function(){
		parts = this.id.split('_');
		doCommand(['setItemState',
			   parts[0],
			   [parseInt(parts[1]), parseInt(parts[2])],
			   true]);
		$('#' + this.id).prop('checked', false);
		$('.outputViewRow').buttonset('refresh');
	});
	$('#' + moduleId + '_module .enableControl').button().click(function(){
		parts = this.id.split('_');
		doCommand(['toggleEnable',
			   parts[0],
			   [parseInt(parts[1]), parseInt(parts[2])]]);
	});

}

function buildPooferModule(moduleData){
	moduleId = moduleData.moduleId
	templateModuleData = {"moduleId" : moduleId, "name" : moduleData.name, "availablePatternNames" : [], "patterns" : [], "inputs" : [], "rows" : []};
	$.each( moduleData.availablePatternNames, function( patternIndex, patternName ) {
		templateModuleData.availablePatternNames.push({"name" : patternName});
	});
	$.each( moduleData.patterns, function( patternInstanceId, patternData ) {
		templatePatternData = {"patternName" : patternData.name, "patternInstanceId" : patternInstanceId, "rowSettings" : [], "moduleId" : moduleId};
		$.each(patternData.rowSettings, function(rowIndex, rowSetting){
			rowData = {"moduleId" : moduleId, "patternInstanceId" : patternInstanceId, "rowIndex" : rowIndex};
			if (rowSetting) rowData['enabled'] = true;
			templatePatternData.rowSettings.push(rowData);
		});
		templateModuleData.patterns.push(templatePatternData);
	});
	$.each( moduleData.protocol.mapping, function( rowIndex, rowData ) {
		templateRowData = {"rowIndex" : rowIndex, "moduleId" : moduleId, "cols" : []};
		$.each( rowData, function( colIndex, colData ) {
			templateRowData.cols.push({"rowIndex" : rowIndex, "moduleId" : moduleId, "colIndex" : colIndex});
			if (moduleData.enabledStatus[rowIndex][colIndex]){
				templateRowData.cols[colIndex]['enabled'] = true;
			}
		});
		templateModuleData.rows.push(templateRowData);
	});
	$('#' + moduleId + '_module').html($('#pooferModuleTemplate').render(templateModuleData));
	initPatternChooser(moduleId);
	$('#' + moduleId + '_removePatternButton').button().click(function(e){
		patternId = $('#' + moduleId + '_patternSelection').val();
		if (patternId && patternId != 'none'){
			doCommand(['removePattern', moduleId, patternId]);
		}
	});
	$.each( moduleData.protocol.mapping, function( rowIndex, rowData ) {
		$('#' + moduleId + '_outputView_row' + rowIndex).buttonset();
		$('#' + moduleId + '_enableView_row' + rowIndex).buttonset();
	});
	$('#' + moduleId + '_module .toggleRowButton').button().click(function(){
		parts = this.id.split('_');
		doCommand(['toggleRowSelection', parts[0], parts[1], parseInt(parts[2])]);
		$('label[for="' + this.id + '"] > .ui-button-text').html('Row ' + parts[2] + ($('#' + this.id).is(":checked")?' Enabled':' Disabled'));
	});
	$('#' + moduleId + '_module .pooferDisplay').click(function(){
		parts = this.id.split('_');
		doCommand(['setItemState', parts[0], [parseInt(parts[1]), parseInt(parts[2])], true]);
		$('#' + this.id).prop('checked', false);
		$('.outputViewRow').buttonset('refresh');
	});
	$('#' + moduleId + '_module .enableControl').button().click(function(){
		parts = this.id.split('_');
		doCommand(['toggleEnable', parts[0], [parseInt(parts[1]), parseInt(parts[2])]]);
	});

}

function buildInputOnlyModule(moduleData){
	$('#' + moduleData.moduleId + '_module').html($('#inputOnlyModuleTemplate').render({"moduleId" : moduleData.moduleId, "name" : moduleData.name}));
}

function buildInputControls(inputInstanceId, inputData){
	if (inputData.inParams){
		$.each( inputData.inParams, function( settingIndex, settingData ) {
			inputId = 'inputInstance' + inputInstanceId + '_input' + settingIndex;
			templateData = $.extend(true, {}, settingData);
			templateData['id'] = inputId;
			templateData['inputInstanceId'] = inputInstanceId;
			templateData['settingIndex'] = settingIndex;

			switch(settingData['type']){
				case 'text':
					if (settingData.subType == 'choice'){
						templateData['choices'] = [];
						$.each(settingData.choices, function(choiceValue, choiceText){
							templateData['choices'].push({'value' : choiceValue, 'name' : choiceText, 'inputInstanceId' : inputInstanceId});
						});
						$('#' + inputId + '_container').append($('#choiceTextTemplate').render(templateData));
						$('#' + inputId + ' .choiceInputItem').button().click(function(){
							parts = this.id.split('_');
							doCommand(['setInputValue', parseInt(parts[0]), parts[1], settingIndex]);
						});
						$('#' + inputId + '_outerContainer').removeClass('ui-widget-content');

					}
					else{
						$('#' + inputId + '_container').append($('#textInputTemplate').render(templateData));
					}
					$('#' + inputId + '_outerContainer').css('height', 'auto');
				break;
				case 'pulse':
					$('#' + inputId + '_container').append($('#buttonTemplate').render(templateData));
					$('#' + inputId).button().click(function(e){
						doCommand(['setInputValue', parseInt(inputInstanceId), true, settingIndex]);
					});
				break;
				case 'toggle':
					if (settingData.currentValue){
						templateData['checked'] = 'checked="checked"';
					}
					else {
						templateData['checked'] = '';
					}
					$('#' + inputId + '_container').append($('#checkButtonTemplate').render(templateData));
					$('#' + inputId).button().click(function(e){
						setInputToggle(inputInstanceId, settingIndex);
					});
				break;
				case 'value':
					$('#' + inputId + '_container').append($('#knobTemplate').render(templateData));
					initKnob(inputId, inputInstanceId, settingIndex);
				break;
			}
			$('#' + inputId + '_description').html(settingData.description);
		});
	}
}

function showGlobalInput(inputInstanceId){
	hideAllInputs();
	inputData = allSculptureData.inputs[inputInstanceId];
	currentView.activeSections['main'] = inputInstanceId
	$('#inputs').detach().appendTo('#globalInput_' + inputInstanceId);
	$('#inputInstance' + inputInstanceId + '_div').css("display", "block");
	$('#inputInstance' + inputInstanceId + '_description').html(inputData.shortDescription);
	$.each(inputData.inParams, function(inputIndex){
		$('#inputInstance' + inputData.instanceId + '_input' + inputIndex + '_outerContainer').css('display', 'block');
	});
	$.each(inputData.outParams, function(outputIndex, outputData){
		id = '#inputInstance' + inputData.instanceId + '_output' + outputIndex + '_container';
		$(id).html('<span class="descriptionText">' + outputData.description + '</span>');
		$(id).css('display', 'block');
	});
}

function hideAllInputs(){

	$.each(allSculptureData.inputs, function(inputInstanceId, inputData){
		$('#inputInstance' + inputInstanceId + '_div').css("display", "none");
		$('#inputInstance' + inputInstanceId + '_outputs').html('');
		$.each(inputData.inParams, function(inputIndex){
			$('#inputInstance' + inputData.instanceId + '_input' + inputIndex + '_outerContainer').css('display', 'none');
		});
		$.each(inputData.outParams, function(outputIndex){
			id = '#inputInstance' + inputData.instanceId + '_output' + outputIndex + '_container';
			$(id).css('display', 'none');
			$(id).html('');
		});

	});

}

function showInput(parentId, parentConfigData, inputChannelId){
	idPrefix  = 'inputInstance' + parentConfigData.inputInstanceId + '_';
	inputData = allSculptureData.inputs[parentConfigData.inputInstanceId];
	$('#' + idPrefix + 'div').css("display", "block");
	if (inputData.type == 'multi'){
		if (inputData.descriptionInPattern){
			$('#' + idPrefix + 'description').html(inputData.descriptionInPattern);
		}
	}
	else {
		$('#' + idPrefix + 'description').html(parentConfigData.description);
	}
	$.each(inputData.inParams, function(inputIndex, inputInputData){
		if (parentConfigData.type=='multi' || inputData.type != 'multi' || $.inArray(parentConfigData.outParamIndex, inputInputData.relevance) > -1){
			$('#inputInstance' + inputData.instanceId + '_input' + inputIndex + '_outerContainer').css('display', 'block');
		}
	});
	if (!inputData.nonChangeable){
		$.each(inputData.outParams, function(outputIndex, outputData){
			if (parentConfigData.type!='multi' && outputIndex == parentConfigData.outParamIndex){
				id = '#inputInstance' + inputData.instanceId + '_output' + outputIndex + '_container';
				$(id).css('display', 'block');
				html = '<div class="inputSubOutputWrapper"><span class="inputDescription">Current type:<br>' + inputData.shortDescription + ' ' + outputData.description + '</span>';
				html += '<button id="' + parentId + '_' + inputChannelId + '_rebindButton" class="rebindButton">Change</button></div>';
				$(id).append(html);
				$('#' + parentId + '_' + inputChannelId + '_rebindButton').button().click(function(e){
					var parts = this.id.split('_');
					showRebindDialog(parts[0], parts[1]=='mainInput'?false:parts[1], parts[2]);
				});
			}
		});
	}

}


function showPatternDetails(moduleId, patternInstanceId){
	hideAllInputs();
	currentView.activeSections[moduleId] = patternInstanceId
	$('#inputs').detach().appendTo('#' + moduleId + '_pattern' + patternInstanceId);
	$.each(allSculptureData.modules[moduleId].patterns[patternInstanceId].inputs, function(inputChannelId, patternInputData){
		showInput(moduleId + '_' + patternInstanceId, patternInputData, inputChannelId);
	});

}
function doCommand(command){
	var commandStr = JSON.stringify(command);
	$('<div>').text('Request submitted: ' + commandStr).prependTo('#logDiv');
	$.ajax(settings.serverUrl + 'doCommand', {
		data : commandStr,
		contentType : 'application/json',
		type : 'POST',
		dataType: 'json',
	}).done(function(result) {
		$('<div>').text('Controller accepted: ' + result.command).prependTo('#logDiv');
		if (result.settingsError){
			$('#settingsStatus').text(result.settingsError).addClass('connectionWarning');
		}
		handleCommandResult(result);
		refreshConnectionStatus();
	}).fail(function(response){
		var detail = response.responseJSON && response.responseJSON.error;
		$('<div>').text('Command failed: ' + command[0] + (detail ? ' — ' + detail : '')).prependTo('#logDiv');
		reloadData();
	});
}
function handleCommandResult(result){
	resultStr = JSON.stringify(result)

	//$('#logDiv').prepend('Result recieved:' + resultStr + '<br>');
	minorCommands = ['setSafeMode', 'setInputValue', 'toggleRowSelection', 'updateSerialConnection', 'setItemState', 'toggleEnable'];
	if ($.inArray(result.command, minorCommands) == -1){
		if (allSculptureData.sculptureId){
			currentView.sculptureIsLoaded = true;
		}
		reloadData();
	}

}
function initPatternChooser(moduleId){
	var chooser = $('#' + moduleId + '_patternChoices');
	if (!isTouchDisplay){
		chooser.menu();
		return;
	}
	// Cog's DRM backend does not provide a native select popup.
	var button = $('<button type="button" class="addPattern">')
		.attr('id', chooser.attr('id'))
		.attr('aria-haspopup', 'dialog')
		.text('Add Pattern');
	chooser.replaceWith(button);
	button.button().click(function(){
		showAddPatternDialog(moduleId);
	});
}

function showAddPatternDialog(moduleId){
	var moduleData = allSculptureData.modules[moduleId];
	var dialog = $('#dialog').empty();
	var submitted = false;
	var names = moduleData.availablePatternNames || [];
	if (!names.length){
		$('<p>').text('No patterns available.').appendTo(dialog);
	}
	$.each(names, function(index, patternName){
		$('<button type="button" class="patternChoice">')
			.text(patternName).appendTo(dialog).button().click(function(){
				if (submitted) return;
				submitted = true;
				dialog.dialog('close');
				doCommand(['addPattern', moduleId, patternName]);
			});
	});
	dialog.dialog({
		title: 'Add Pattern: ' + moduleData.name,
		dialogClass: 'patternChooserDialog',
		modal: true,
		draggable: false,
		resizable: false,
		width: Math.min(360, $(window).width() - 24),
		maxHeight: $(window).height() - 24,
		buttons: {
			Cancel: function(){ $(this).dialog('close'); }
		},
		close: function(){
			$(this).empty().dialog('destroy');
		}
	});
}

function addPattern(moduleId){
	inputId = '#' + moduleId + '_patternChoices';
	if ($(inputId).val() != 'none'){
		doCommand(['addPattern', moduleId, $(inputId).val()]);
		$(inputId).val('none');
	}
}
function setInputValue(inputInstanceId, settingIndex){
	htmlId = '#inputInstance' + inputInstanceId + '_input' + settingIndex;
	doCommand(['setInputValue', parseInt(inputInstanceId), parseInt($(htmlId).val()), parseInt(settingIndex)]);
}
function setInputToggle(inputInstanceId, settingIndex){
	htmlId = '#inputInstance' + inputInstanceId + '_input' + settingIndex;
	doCommand(['setInputValue', parseInt(inputInstanceId), $(htmlId).is(":checked"), parseInt(settingIndex)]);
}
function updateStatusDisplay(){
	if (allSculptureData.activeSculptureId){
		$.each(allSculptureData.sculptures[allSculptureData.activeSculptureId].modules, function(moduleId, moduleData){
			$.each(moduleData.currentOutputState, function(rowIndex, rowData){
				$.each(rowData, function(colIndex, colData){
					id =  moduleId + '_outputView_row' + rowIndex + '_col' + colIndex;
					$('#' + id).prop('checked', colData).button('refresh');
				});
			});
		});
	}
}

function initKnob(htmlId, inputInstanceId, settingIndex){
	htmlId = '#' + htmlId;
	$(htmlId).knob({
		release : function (value) {
			setInputValue(inputInstanceId, settingIndex);
		},
		draw : function () {

				// "tron" case
				if(this.$.data('skin') == 'tron') {

						this.cursorExt = 0.3;

						var a = this.arc(this.cv)  // Arc
								, pa                   // Previous arc
								, r = 1;

						this.g.lineWidth = this.lineWidth;

						if (this.o.displayPrevious) {
								pa = this.arc(this.v);
								this.g.beginPath();
								this.g.strokeStyle = this.pColor;
								this.g.arc(this.xy, this.xy, this.radius - this.lineWidth, pa.s, pa.e, pa.d);
								this.g.stroke();
						}

						this.g.beginPath();
						this.g.strokeStyle = r ? this.o.fgColor : this.fgColor ;
						this.g.arc(this.xy, this.xy, this.radius - this.lineWidth, a.s, a.e, a.d);
						this.g.stroke();

						this.g.lineWidth = 2;
						this.g.beginPath();
						this.g.strokeStyle = this.o.fgColor;
						this.g.arc( this.xy, this.xy, this.radius - this.lineWidth + 1 + this.lineWidth * 2 / 3, 0, 2 * Math.PI, false);
						this.g.stroke();

						return false;
				}
		}
	});
}
