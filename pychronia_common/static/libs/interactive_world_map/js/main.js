

var width=0;
var height=0;
var newWidth = 0;
var newHeight = 0;
var $section ;
var $panzoom ;


var isTouchDevice = (window.ontouchstart !== undefined);


var displayTooltip = function(e){
    //console.log("Pointer mousemove to", e.target);
    var target = $(e.target);
    var tooltip = $("#world-map-tooltip");
    if(target.attr("class")=='coords-ref' && target.attr('alt') !== ""){
        //console.log("Pointer at coords-ref");
        tooltip.html(target.attr('alt'));
        tooltip.css('visibility','visible');
        if (!isTouchDevice) {
            tooltip.css('top',''+e.clientY+'px');  // will fallback to 0 on touch devices
            tooltip.css('left',''+(e.clientX+5)+'px');  // will fallback to 0 on touch devices
        }
    } else {
        tooltip.css('visibility','hidden');
    }

    // var percentWidth= (e.offsetX / width)*100;
    // var percentHeight= (e.offsetY / height)*100;
    //    $("#text").html('offsetX: '+e.offsetX+' offsetY: '+e.offsetY+
    //            'clientX: '+e.clientX+' clientY: '+e.clientY+
    //        ' width '+width+' height '+height+' percentWidth '+percentWidth+' percentHeight '+percentHeight+' newwidth' +newWidth+' newheight' +newHeight);
    //

}

$('html').on('mousemove', displayTooltip);
$('html').on('touchend', displayTooltip);


$(document).ready(function(){

    var minScale = 1, maxScale = 5, increment = 0.1;

    $('map').imageMapResize();
    //$('map')[0]._resize();

    var panzoom = $('.panzoom');
    panzoom.panzoom({
                    $zoomIn: $(".zoom-buttons .zoom-in"),
                    $zoomOut: $(".zoom-buttons .zoom-out"),
                    $reset: $(".zoom-buttons .reset"),
                    increment: 3*increment,
                    minScale: minScale,
                    maxScale: maxScale
                   });

    panzoom.parent().on('mousewheel.focal', function(e) {
                    e.preventDefault();
                    var delta = e.delta || e.originalEvent.wheelDelta;
                    var zoomOut = delta ? delta < 0 : e.originalEvent.deltaY > 0;
                    //console.log("we panzoom wheel", delta, zoomOut);
                    panzoom.panzoom('zoom', zoomOut, {
                        focal: e,
                        transition: true,
                        increment: increment,
                        minScale: minScale,
                        maxScale: maxScale,
                    });
                });

});

