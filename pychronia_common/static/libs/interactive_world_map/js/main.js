

var width=0;
var height=0;
var newWidth = 0;
var newHeight = 0;
var $section ;
var $panzoom ;
    
$('html').on('mousemove', function(e){
    
    var percentWidth= (e.offsetX / width)*100;
    var percentHeight= (e.offsetY / height)*100;

    if($(e.target).attr("class")=='cardRef'){
        //console.log("cardref");
        $("#small_infobulle").html($(e.target).attr('alt'));
        $("#small_infobulle").css('visibility','visible');
        $("#small_infobulle").css('top',''+e.clientY+'px');
        $("#small_infobulle").css('left',''+e.clientX+'px');

        $(e.target).on('mouseleave',function(){
            $("#small_infobulle").css('visibility','hidden');
        });
    };

    //    $("#text").html('offsetX: '+e.offsetX+' offsetY: '+e.offsetY+
    //            'clientX: '+e.clientX+' clientY: '+e.clientY+
    //        ' width '+width+' height '+height+' percentWidth '+percentWidth+' percentHeight '+percentHeight+' newwidth' +newWidth+' newheight' +newHeight);
    //

});

$(document).ready(function(){

    var minScale = 1, maxScale = 3, increment = 0.1;

    $('map').imageMapResize();

    $section = $('section').first();
    $section.find('.panzoom').panzoom({
                                        $zoomIn: $section.find(".zoom-in"),
                                        $zoomOut: $section.find(".zoom-out"),
                                        $reset: $section.find(".reset"),
                                        increment: 3*increment,
                                        minScale: minScale,
                                        maxScale: maxScale,
                                      });


    $section = $('#focal');
    $panzoom = $section.find('.panzoom').panzoom();

    $panzoom.parent().on('mousewheel.focal', function(e) {
                    e.preventDefault();
                    var delta = e.delta || e.originalEvent.wheelDelta;
                    var zoomOut = delta ? delta < 0 : e.originalEvent.deltaY > 0;
                    //console.log("we panzoom wheel", delta, zoomOut);
                    $panzoom.panzoom('zoom', zoomOut, {
                        focal: e,
                        transition: true,
                        increment: increment,
                        minScale: minScale,
                        maxScale: maxScale,
                    });
                });

});

