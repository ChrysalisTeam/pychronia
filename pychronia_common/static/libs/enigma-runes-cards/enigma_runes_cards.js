
// VARIABLE enigmaRunesCardsAssetsRoot must be GLOBALLY defined //
var enigmaRunesCardsImgRoot = enigmaRunesCardsAssetsRoot+"imgs/";
var enigmaRunesCardsSndRoot = enigmaRunesCardsAssetsRoot+"snds/";

var chimeSnd = new Audio(enigmaRunesCardsSndRoot + "chime.mp3"); // buffers automatically when created
chimeSnd.volume = 0.3;

var victorySnd = new Audio(enigmaRunesCardsSndRoot + "angels.mp3"); // buffers automatically when created

function createPuzzle() {

    card_hand = {};
    card_hand.AVAILABLE_SYMBOLS = ['arrow.png', 'circle.png', 'diamond.png', 'heart.png', 'moon.png', 'pentagon.png', 'square.png', 'star.png', 'triangle.png']
    card_hand.SUCCESS_SYMBOLS = ['moon.png', 'heart.png', 'arrow.png', 'circle.png']

    card_hand.PUZZLE_CURRENT_STATE = new Array(card_hand.SUCCESS_SYMBOLS.length);
    for (var i = 0; i < card_hand.SUCCESS_SYMBOLS.length; i++){
        card_hand.PUZZLE_CURRENT_STATE[i] = new Array(card_hand.SUCCESS_SYMBOLS.length);
    }

    return card_hand;
}


function get_random_image(){
    var index = Math.floor(Math.random() * card_hand.AVAILABLE_SYMBOLS.length);
    var image = enigmaRunesCardsImgRoot + card_hand.AVAILABLE_SYMBOLS[index]
    return image
}


function drawCardHand(card_hand){
    var content = "<table>";
    var size = 90;

    for (var i = 0; i < card_hand.SUCCESS_SYMBOLS.length; i++) {
        var image = get_random_image()
        card_hand.PUZZLE_CURRENT_STATE[i] = image.split("/").pop();
        content += "<td> <img id='card_" + i +"' width=" + size + "px src='" + image + "'> </td>"
    }

    content += "</table>"
    $('#enigma-container').append(content);
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
            var currentIndex = card_hand.AVAILABLE_SYMBOLS.indexOf(image);
            var newIndex = (currentIndex + 1) % card_hand.AVAILABLE_SYMBOLS.length;
            newImage = enigmaRunesCardsImgRoot+card_hand.AVAILABLE_SYMBOLS[newIndex];

            card_hand.PUZZLE_CURRENT_STATE[number] = newImage.split("/").pop()
            $('#'+id).attr("src", newImage);

            var currentState = Counter(card_hand.PUZZLE_CURRENT_STATE);
            var successState = Counter(card_hand.SUCCESS_SYMBOLS);
            var successful = object_equals(currentState, successState)

            if (successful == true){
                $("#victory-overlay").css("display", "block");

                victorySnd.play();
				$("img").off('click');
            }

            $('#'+id).fadeIn('fast');
        });

        chimeSnd.pause();
        chimeSnd.currentTime = 0;
        chimeSnd.play();

    });
}


function resetEnigmaRunesCards(){
	$("#victory-overlay").css("display", "none");
	card_hand=createPuzzle();
	drawCardHand(card_hand);
	clickEvent();
}


function launchEnigmaRunesCards(){
    card_hand = createPuzzle();
    drawCardHand(card_hand);
    clickEvent();
}


$(launchEnigmaRunesCards);
