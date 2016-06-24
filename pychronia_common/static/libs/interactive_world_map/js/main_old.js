

var zoomCarte=100;
var mousedownCarte=false;



$("html").on('mousewheel',function(event) {
    if($(event.target).attr('id')=="conteneurCarte")
    {
        event.preventDefault();
        //event.propagationStop();
        //console.log(event.deltaX, event.deltaY, event.deltaFactor);
        //console.log(event);
        zoomCarte += event.deltaY*10;
        console.log(zoomCarte);
         $(event.target).css('background-size',""+zoomCarte+"%");
    }
});
$("html").on('mousedown',function(event){
    if($(event.target).attr('id')=="conteneurCarte")
    {
        event.preventDefault();
        mousedownCarte=true;
    //console.log(event);
    }
});
$("html").on('mousemove',function(event){
    if(mousedownCarte){
        console.log(event);
        var strx=$("#conteneurCarte").css('background-position-x');
        var stry=$("#conteneurCarte").css('background-position-y');
        strx=strx.replace("%","");
        stry=stry.replace("%","");
        var x=parseInt(strx)-event.offsetX;
        var y=parseInt(stry)-event.offsetY;
        console.log(""+x+"%");
        $("#conteneurCarte").css('background-position-x',""+x+"%");
        $("#conteneurCarte").css('background-position-y',""+y+"%");
    }
    
});
$("html").on('mouseup',function(event){
    //if($(event.target).attr('id')=="conteneurCarte")
    //{
      //  event.preventDefault();
        mousedownCarte=false;
    //console.log(event);
   // }
});

    

$(document).ready(function(){
    
    console.log($("#conteneurCarte").width());
    console.log($("#conteneurCarte").height());
    
    console.log($(".carteMonde").css('background-size'));
    console.log($(".carteMonde").css('height'));
    
    
    
    console.log($("#conteneurCarte").css('background-position-x'));
        //$("#conteneurCarte").css('background-position-x',"0px");
        //$("#conteneurCarte").css('background-position-y',"0px");
        
        $("#conteneurCarte").css('background-position-x',($("#conteneurCarte").width()/8)+"px");
        $("#conteneurCarte").css('background-position-y',($("#conteneurCarte").height()/8)+"px");
        
        
    
});
