var settings = {
	'serverUrl' : '/'
};
var allSculptureData = false;
var currentView = {'activeTab' : false, 'activeModule' : false, activeSections : {}, sculptureIsLoaded:false}
var serverSentEventStream = false;


function convertRGBTupleToRGBString(tuple) {
	return "rgb(" + tuple[0] + "," + tuple[1] + "," + tuple[2] + ")";
};


function handleDataStreamEvent(data){
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
					element.style.background =
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
		autoOpen: true,
		height: 300,
		width: 350,
		modal: true,
		buttons: {
			"Update": function() {
				doNewInputBinding(moduleId, patternInstanceId, inputChannelId);
				$(this).dialog("close");
			},
			"Cancel": function() {
				$(this).dialog("close");
			}
		},
		close: function(event, ui) {
			$(this).empty().dialog('destroy');
		}
	});
}
function showGlobalInputDialog(){
	selectData = {'id' : 'inputSelector', 'onChange' : 'onChange = "showInputParamsForm()"', 'options' : [{'description' : 'Select Input', 'value' : 'none'}]};
	$.each(allSculptureData.availableGlobalInputs, function(typeIndex, typeData){
		selectData.options.push({'description' : allSculptureData.availableInputTypes[typeData[0]][typeData[1]].longDescription, 'value' : JSON.stringify(['new', typeData[0], typeData[1]])});
	});
	$('#dialog').append($('#selectTemplate').render(selectData));
	$('#dialog').append('<div id="dialogInputs"></div>');
	$('#dialog').dialog({
		autoOpen: true,
		height: 300,
		width: 350,
		modal: true,
		buttons: {
			"Update": function() {
				doNewInputBinding('main');
				$(this).dialog("close");
			},
			"Cancel": function() {
				$(this).dialog("close");
			}
		},
		close: function(event, ui) {
			$(this).empty().dialog('destroy');
		}
	});
}

function doNewInputBinding(moduleId, patternInstanceId, inputChannelId){
	values = JSON.parse($('#inputSelector').val());
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
	values = JSON.parse($('#inputSelector').val());
	formFields = [];
	if (values[0] == 'new'){
		inputTypeData = allSculptureData.availableInputTypes[values[1]][values[2]];
		if (inputTypeData.setupParamsNeeded){
			$.each(inputTypeData.setupParamsNeeded, function (paramIndex, paramData){
				fieldData = {"id" : "inputDefinitionMainParam" + paramData[2], "label" : paramData[1]}
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
	reloadData();
	serverSentEventStream = new EventSource('/dataStream');
	serverSentEventStream.onmessage = function (event) {
		handleDataStreamEvent(JSON.parse(event.data));
	};
	serverSentEventStream.onerror = function () {
		$('#logDiv').prepend('<span style="font-weight:bold; font-color:FFCD4D">Connection error</span><br>');
	};

}

function setCurrentModuleView(moduleId){
	currentView.activeModule = moduleId;
	if (currentView.activeSections[moduleId]){
		$('#' + currentView.activeSections[moduleId] + '_heading').click();
	}
	else if (allSculptureData.modules[moduleId].inputs){
		hideAllInputs();
		$('#inputs').detach().appendTo('#' + moduleId + '_inputs');
		$.each(allSculptureData.modules[moduleId].inputs, function(inputChannelId, inputData){
			showInput(moduleId + '_mainInput', inputData, inputChannelId);
		});
	}
}

function reloadData(){
	$.ajax(settings.serverUrl + 'getData', {
		dataType: 'json'
	}).done(function(result) {
		allSculptureData = result
		buildAll();
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
		$( ".accordion" ).accordion({
			collabsible : true,
			active : 'none'
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
			parts = this.id.split('_');
			doCommand(['removePattern', parts[0], parts[1]]);
		});
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
		$('.serialAdaptorUpdateButton').button().click(function(){
			adaptorId = this.id.split('_')[0];
			doCommand(['updateSerialConnection', adaptorId, {'ports' : $('#' + adaptorId + 'Ports').val().split(' '), 'baudrate' : $('#' + adaptorId + 'Baudrate').val()}]);
		});
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
	$('#' + moduleId + '_patternChoices').menu();
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
	$('#' + moduleId + '_patternChoices').menu();
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
	commandStr = JSON.stringify(command)
	$('#logDiv').prepend('Command sent:' + commandStr + '<br>');
	$.ajax(settings.serverUrl + 'doCommand', {
		data : commandStr,
		contentType : 'application/json',
		type : 'POST',
		dataType: 'json',
	}).done(function(result) {
		handleCommandResult(result);
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
