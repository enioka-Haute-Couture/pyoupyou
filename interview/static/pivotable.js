 function drawPivot(data, rows, cols, rendererName, aggregatorName, vals, options, lang, filter) {
     var renderers = $.extend($.pivotUtilities.renderers, $.pivotUtilities.plotly_renderers, $.pivotUtilities.export_renderers);
     if (typeof filter == "undefined") { var filter = () => true; }
     if (typeof options == "undefined") { var options = {}; }
     $("#pivotable-output").pivotUI(
         data,
         {
             rows: rows,
             cols: cols,
             renderers: renderers,
             rendererOptions: options,
             unusedAttrsVertical: false,
             rendererName: rendererName,
             aggregatorName: aggregatorName,
             onRefresh: hideTotal,
             vals: vals,
             inclusions: options['inclusions'] || '',
             exclusions: options['exclusions'] || '',
             rowOrder: options['rowOrder'] || 'key_a_to_z',
             colOrder: options['colOrder'] || 'key_a_to_z',
             filter: filter,
         },
         true,
         lang
     );
 }
 function hideTotal(config) {
     // Hide total when it does not have any sense
     if (config["rendererOptions"]["hideRowTotal"]) {
         $(".pvtTotal.rowTotal").css("display", "None");
         $(".pvtRowTotalLabel").css("display", "None");
     }
     if (config["rendererOptions"]["hideColTotal"]) {
         $(".pvtTotal.colTotal").css("display", "None");
         $(".pvtColTotalLabel").css("display", "None");
     }
     if (config["rendererOptions"]["hideGrandTotal"]) {
         $(".pvtGrandTotal").css("display", "None");
     }
 }
