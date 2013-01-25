// jQuery hcSticky
// =============
// Version: 1.1.9
// Copyright: Some Web Media
// Author: Some Web Guy
// Author URL: http://twitter.com/some_web_guy
// Website: http://someweblog.com/
// Plugin URL: http://someweblog.com/hcsticky-jquery-floating-sticky-plugin/
// License: Released under the MIT License www.opensource.org/licenses/mit-license.php
// Description: Makes elements on your page float as you scroll

(function($){
    /*----------------------------------------------------
                        GLOBAL FUNCTIONS
    ----------------------------------------------------*/
    
    // check for scroll direction and speed
    var getScroll = function() {
        if (typeof getScroll.x == 'undefined') {
            getScroll.x = window.pageXOffset;
            getScroll.y = window.pageYOffset;
        }
        if (typeof getScroll.distanceX == 'undefined') {
            getScroll.distanceX = window.pageXOffset;
            getScroll.distanceY = window.pageYOffset;
        } else {
            getScroll.distanceX = window.pageXOffset - getScroll.x;
            getScroll.distanceY = window.pageYOffset - getScroll.y;
        }
        var diffX = getScroll.x - window.pageXOffset,
            diffY = getScroll.y - window.pageYOffset;
        getScroll.direction = diffX < 0 ? 'right' :
            diffX > 0 ? 'left' :
            diffY <= 0 ? 'down' :
            diffY > 0 ? 'up' : 'first';
        getScroll.x = window.pageXOffset;
        getScroll.y = window.pageYOffset;
    };
    $(window).on('scroll', getScroll);
    
    // get original css (auto, %)
    var getCSS = function(el,style) {
        if (typeof el.cssClone == 'undefined') {
            el.cssClone = el.clone().css('display','none');
            el.after(el.cssClone);
        }
        var clone = el.cssClone[0];
        if(typeof style != 'undefined') {
            var value;
            if (clone.currentStyle) {
                value = clone.currentStyle[style.replace(/-\w/g, function(s){return s.toUpperCase().replace('-','')})];
            } else if (window.getComputedStyle) {
                value = document.defaultView.getComputedStyle(clone,null).getPropertyValue(style);
            }
            value = (/margin/g.test(style)) ? ((parseInt(value) === el[0].offsetLeft) ? value : 'auto') : value;
        }
        return {
            value: value || null,
            remove: function() {
                el.cssClone.remove();
            }
        };
    };
    
    /*----------------------------------------------------
                        JQUERY PLUGIN
    ----------------------------------------------------*/
    
    $.fn.extend({
        
        hcSticky: function(options, reinit){
            
	    // check if selected element exist in DOM, user doesn't have to worry about that
	    if (this.length == 0)
		return this;
	    
            var settings = options || {},
                running = (this.data('hcSticky')) ? true : false,
                $window = $(window),
                $document = $(document);
            
            if (typeof settings == 'string') {
                switch(settings){
                    case 'reinit':
                        // detach scroll event
                        $window.off('scroll', this.data('hcSticky').f);
                        // call itself to start again
                        return this.hcSticky({},true);
                        break;
                    case 'off':
                        this.data('hcSticky', $.extend(this.data('hcSticky'),{on:false}));
                        break;
                    case 'on':
                        this.data('hcSticky', $.extend(this.data('hcSticky'),{on:true}));
                        break;
                }
                return this;
            } else if (typeof settings == 'object') {
                if (!running) {
                    // these are the default settings
                    this.data('hcSticky', $.extend({
                        top: 0,
                        bottom: 0,
                        bottomEnd: 0,
                        bottomLimiter: null,
                        innerTop: 0,
                        innerSticker: null,
                        className: 'sticky',
                        wrapperClassName: 'wrapper-sticky',
                        noContainer: false,
                        followScroll: true,
			onStart: function(){},
			onStop: function(){},
                        on: true
                    }, settings));
                    // check for bottom limiter
                    var $bottom_limiter = this.data('hcSticky').bottomLimiter;
                    if ($bottom_limiter !== null && this.data('hcSticky').noContainer) {
                        this.data('hcSticky', $.extend(this.data('hcSticky'),{bottomEnd:$document.height() - $($bottom_limiter).offset().top}));
                    }
                } else {
                    // update existing settings
                    this.data('hcSticky', $.extend(this.data('hcSticky'),settings));
                }
                // if already running and not reinited don't go further all we needed was to update settings
                if (running && !reinit) {
                    return this;
                }
            }
	    
	    // do our thing
            return this.each(function(){
                
                var $this = $(this),
                    // get wrapper if already created, if not create it
                    $wrapper = (function(){
                            // wrapper exists
                            var $this_wrapper = $this.parent('.'+$this.data('hcSticky').wrapperClassName);
                            if ($this_wrapper.length > 0) {
                                $this_wrapper.css({
                                    'height': $this.outerHeight(true),
                                    'width': (function(){
                                        // check if wrapper already has width in %
                                        var width = getCSS($this_wrapper,'width').value;
                                        getCSS($this_wrapper).remove();
                                        if (width.indexOf('%') >= 0 || width == 'auto') {
                                            $this.css('width',$this_wrapper.width());
                                            return width;
                                        } else {
                                            return $this.outerWidth(true);
                                        }
                                    })()
                                });
                                return $this_wrapper;
                            } else {
                                return false;
                            }
                        })() || (function(){
                            // wrapper doesn't exist, create it
                            var $this_wrapper = $('<div>',{'class':$this.data('hcSticky').wrapperClassName}).css({
                                'height': $this.outerHeight(true),
                                'width': (function(){
                                    // check if element has width in %
                                    var width = getCSS($this,'width').value;
                                    if (width.indexOf('%') >= 0 || width == 'auto') {
                                        $this.css('width',$this.width());
                                        return width;
                                    } else {
                                        // check if margin is set to 'auto'
                                        var margin = getCSS($this,'margin-left').value;
                                        return (margin == 'auto') ? $this.outerWidth() : $this.outerWidth(true);
                                    }
                                })(),
                                'margin': (getCSS($this,'margin-left').value) ? 'auto' : null,
                                'position': (function(){
                                    var position = $this.css('position');
                                    return position == 'static' ? 'relative' : position;
                                })(),
                                'float': $this.css('float') || null,
                                'left': getCSS($this,'left').value,
                                'right': getCSS($this,'right').value,
                                'top': getCSS($this,'top').value,
                                'bottom': getCSS($this,'bottom').value
                            });
                            $this.wrap($this_wrapper);
                            // return appended element
                            return $this.parent();
                        }
                    )(),
                    // functions for attachiung and detaching sticky
                    setFixed = function(args){
			// check if already floating
			if ($this.hasClass($this.data('hcSticky').className))
			    return;
                        args = args || {};
                        $this.css({
                            position: 'fixed',
                            top: args.top || 0,
                            left: args.left || $wrapper.offset().left
                        }).addClass($this.data('hcSticky').className);
			// run function for start event of sticky
			$this.data('hcSticky').onStart.apply($(this));
                    },
                    reset = function(args){
                        args = args || {};
                        $this.css({
                            position: args.position || 'absolute',
                            top: args.top || 0,
                            left: args.left || 0
                        }).removeClass($this.data('hcSticky').className);
			// run function for stop event of sticky
			$this.data('hcSticky').onStop.apply($(this));
                    };
                
                // clear clone element we created for geting real css value
                getCSS($this).remove();
                // reset sticky content
                $this.css({top:'auto',bottom:'auto',left:'auto',right:'auto'});
                
                // start the magic
                var f = function(init){
                    
                    // get referring element
                    $referrer = ($this.data('hcSticky').noContainer) ? $document : $wrapper.parent();
                    
                    // check if we need to run sticky
                    if (!$this.data('hcSticky').on || $this.outerHeight(true) >= $referrer.height())
                        return;

                    var top_spacing = ($this.data('hcSticky').innerSticker) ? $($this.data('hcSticky').innerSticker).position().top : (($this.data('hcSticky').innerTop) ? $this.data('hcSticky').innerTop : 0),
                        //wrapper_inner_top = $wrapper.offset().top + ($this.data('hcSticky').noContainer ? 0 : (parseInt($referrer.css('borderTopWidth')) + parseInt($referrer.css('padding-top')) + parseInt($referrer.css('margin-top')))), 
			wrapper_inner_top = $wrapper.offset().top,
                        bottom_limit = $referrer.height() - $this.data('hcSticky').bottomEnd + ($this.data('hcSticky').noContainer ? 0 : wrapper_inner_top),
                        top_limit = $wrapper.offset().top - $this.data('hcSticky').top + top_spacing,
                        this_height = $this.outerHeight(true) + $this.data('hcSticky').bottom,
                        window_height = $window.height(),
                        offset_top = $window.scrollTop(),
                        this_document_top = $this.offset().top,
                        this_window_top = this_document_top - offset_top,
                        bottom_distance; // this is for later
                    
                    
                    if (offset_top >= top_limit) {
                        
                        // I have no fuckin idea what am I checking here, but it works :)
                        if (bottom_limit + $this.data('hcSticky').bottom - ($this.data('hcSticky').followScroll ? 0 : $this.data('hcSticky').top) <= offset_top + this_height - top_spacing - ((this_height - top_spacing > window_height - (top_limit - top_spacing) && $this.data('hcSticky').followScroll) ? (((bottom_distance = this_height - window_height - top_spacing) > 0) ? bottom_distance : 0) : 0)) {   
                            // bottom reached end
                            reset({
                                top: bottom_limit - this_height + $this.data('hcSticky').bottom - wrapper_inner_top
                            });
                        } else if (this_height - top_spacing > window_height && $this.data('hcSticky').followScroll ) {
                            // sidebar bigger than window with follow scroll on
                            if (this_window_top + this_height <= window_height) {
                                if (getScroll.direction == 'down') {
                                    // scroll down
                                    setFixed({
                                        top: window_height - this_height
                                    });
                                } else {
                                    // scroll up
                                    if (this_window_top < 0 && $this.css('position') == 'fixed') {
                                        reset({
                                            top: this_document_top - (top_limit + $this.data('hcSticky').top - top_spacing) - getScroll.distanceY
                                        });
                                    }
                                }
                            // sidebar smaller than window or follow scroll turned off
                            } else {
                                if (getScroll.direction == 'up' && this_document_top >= offset_top + $this.data('hcSticky').top - top_spacing) {
                                    // scroll up
                                    
                                    setFixed({
                                        top: $this.data('hcSticky').top - top_spacing
                                    });
                                } else if (getScroll.direction == 'down' && this_document_top + this_height > window_height && $this.css('position') == 'fixed') {
                                    // scroll down
                                    reset({
                                        top: this_document_top - (top_limit + $this.data('hcSticky').top - top_spacing) - getScroll.distanceY
                                    });
                                }
                            }
                        } else {
                            // starting (top) fixed position
                            setFixed({
                                top: $this.data('hcSticky').top - top_spacing
                            });
                        }
                    } else {
                        // reset bar
                        reset();
                    }

                    // just in case someone set "top" larger than elements style top
                    if (init === true) {
                        $this.css('top', ($this.css('position') == 'fixed') ? $this.data('hcSticky').top - top_spacing : 0);
                    }

                };
                
                $window.on('resize', function(){
                    if ($this.css('position') == 'fixed') {
                        $this.css('left', $wrapper.offset().left);
                    } else {
                        $this.css('left', 0);
                    }
                });
                
                // set scroll empty function in case we need to reinit plugin
                $this.data('hcSticky', $.extend($this.data('hcSticky'),{f:function(){}}));
                // set scroll function
                $this.data('hcSticky', $.extend($this.data('hcSticky'),{f:f}));
                // run it for the first time to disable glitching
                $this.data('hcSticky').f(true);
                // attach function to scroll event
                $window.on('scroll', $this.data('hcSticky').f);
		
            });
        }
    });

})(jQuery);