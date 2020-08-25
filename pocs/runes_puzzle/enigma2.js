var images = "card_images/";

function createPuzzle() {

    card_hand = {};
    card_hand.AVAILABLE_SYMBOLS = ['arrow.png', 'circle.png', 'diamond.png', 'heart.png', 'moon.png', 'oval.png', 'pentagon.png', 'square.png', 'star.png', 'triangle.png']
    card_hand.SUCCESS_SYMBOLS = ['moon.png', 'heart.png', 'arrow.png', 'circle.png']

    card_hand.PUZZLE_CURRENT_STATE = new Array(card_hand.SUCCESS_SYMBOLS.length);
    for (var i = 0; i < card_hand.SUCCESS_SYMBOLS.length; i++){
        card_hand.PUZZLE_CURRENT_STATE[i] = new Array(card_hand.SUCCESS_SYMBOLS.length);
    }

    return card_hand;
}


function initialize_images(){
    var index = Math.floor(Math.random() * card_hand.AVAILABLE_SYMBOLS.length);
    var image = images + card_hand.AVAILABLE_SYMBOLS[index]
    return image
}


function drawCardHand(card_hand){
    var content = "<table>";
    var size = 150;

    for (var i = 0; i < card_hand.SUCCESS_SYMBOLS.length; i++) {
        var image = initialize_images()
        card_hand.PUZZLE_CURRENT_STATE[i] = image.split("/").pop();
        content += "<td> <img id='card_" + i +"' height=" + size + "px src='" + image + "'> </td>"
    }

    content += "</table>"
    $('#cards').append(content);
}


function Counter(array) {
    var count = {};
    array.forEach(val => count[val] = (count[val] || 0) + 1);
    return count;
}


function object_equals( x, y ) {
  if ( x === y ) return true;
    // if both x and y are null or undefined and exactly the same

  if ( ! ( x instanceof Object ) || ! ( y instanceof Object ) ) return false;
    // if they are not strictly equal, they both need to be Objects

  if ( x.constructor !== y.constructor ) return false;
    // they must have the exact same prototype chain, the closest we can do is
    // test there constructor.

  for ( var p in x ) {
    if ( ! x.hasOwnProperty( p ) ) continue;
      // other properties were tested using x.constructor === y.constructor

    if ( ! y.hasOwnProperty( p ) ) return false;
      // allows to compare x[ p ] and y[ p ] when set to undefined

    if ( x[ p ] === y[ p ] ) continue;
      // if they have the same strict value or identity then they are equal

    if ( typeof( x[ p ] ) !== "object" ) return false;
      // Numbers, Strings, Functions, Booleans must be strictly equal

    if ( ! object_equals( x[ p ],  y[ p ] ) ) return false;
      // Objects and Arrays must be tested recursively
  }

  for ( p in y )
    if ( y.hasOwnProperty( p ) && ! x.hasOwnProperty( p ) )
      return false;
        // allows x[ p ] to be set to undefined

  return true;
}


function clickEvent(){
    $("img").click(function() {
        var win = false;
        var imageFront = $(this).attr("src");
        var id = $(this).attr("id");
        var image = imageFront.split("/").pop()

        $('#'+id).fadeOut('fast', function() {
            var number = parseInt((id).substr(5))
            actualIndex = card_hand.AVAILABLE_SYMBOLS.indexOf(image);

            if (actualIndex == 9){
                newImage = images+card_hand.AVAILABLE_SYMBOLS[0];
            }
            else{
                newImage = images+card_hand.AVAILABLE_SYMBOLS[actualIndex+1];
            }

            card_hand.PUZZLE_CURRENT_STATE[number] = newImage.split("/").pop()
            $('#'+id).attr("src", newImage);

            var currentState = Counter(card_hand.PUZZLE_CURRENT_STATE);
            var successState = Counter(card_hand.SUCCESS_SYMBOLS);
            var successful = object_equals(currentState, successState)

            if (successful == true){
                $("#overlay").css("display", "block");
				var snd = new Audio("audios\\chime.mp3"); // buffers automatically when created
				snd.play();
				$("img").off('click');
            }

        $('#'+id).fadeIn('fast');
        });

        var snd = new Audio("audios\\pi.mp3"); // buffers automatically when created
		snd.play();

    });
}


function reset(){
	$("table").remove();
	$("#overlay").css("display", "none");
	card_hand=createPuzzle();
	drawCardHand(card_hand);
	clickEvent();
}


function main(){
    card_hand = createPuzzle();
    drawCardHand(card_hand);
    clickEvent();
}


main();