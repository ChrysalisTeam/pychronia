# -*- coding: utf-8 -*-

import re, copy
from django_select2 import HeavySelect2MultipleChoiceField, Select2MultipleWidget
from django_select2.widgets import MultipleSelect2HiddenInput, Select2Mixin
from django.utils.translation import ugettext_lazy
from django.core.exceptions import ValidationError


class Select2TagsWidget(Select2Mixin, MultipleSelect2HiddenInput): ##SpecialHiddenInput): ###forms.HiddenInput): ###MultipleSelect2HiddenInput):

    input_type = 'text'  # additioanl security...

    def init_options(self):
        self.options.update({"closeOnSelect": True, # maximumSelectionSize buggy when not closeOnSelect, so we workaround...
                             "maximumSelectionSize":-1, # overridden by form field
                             "separator": '*START*django_select2.MULTISEPARATOR*END*',
                            "tokenSeparators": [",", ";"], # spaces are NOT separators
                            "tags": []}) # overridden by field

    def set_choice_tags(self, tags):
        self.options["tags"] = tags

    def set_max_selection_size(self, size):
        self.options["maximumSelectionSize"] = size

    def render_inner_js_code(self, id_, *args):
        fieldset_id = re.sub(r'-\d+-', '_', id_).replace('-', '_')
        if '__prefix__' in id_:
            return ''
        else:
            js = u'''
                  window.django_select2.%s = function (selector, fieldID) {
                    var hashedSelector = "#" + selector;
                    $(hashedSelector).data("field_id", fieldID);
                  ''' % (fieldset_id)
            js += super(Select2TagsWidget, self).render_inner_js_code(id_, *args)
            js += '};'
            js += 'django_select2.%s("%s", "%s");' % (fieldset_id, id_, id_)
            return js



class Select2TagsField(HeavySelect2MultipleChoiceField):
    widget = Select2TagsWidget

    default_error_messages = {
        'too_many': ugettext_lazy(u'Too many values sent.'),
    }

    def __init__(self, **kwargs):

        choice_tags = kwargs.pop("choice_tags", []) # done first
        max_selection_size = kwargs.pop("max_selection_size", -1) # done first

        if kwargs.get('widget', None) is None:
            # we override the nasty behaviour of HeavySelect2MultipleChoiceField mixins
            #who expect data_view to be sent to widget
            kwargs['widget'] = self.widget()

        super(Select2TagsField, self).__init__(**kwargs)

        self.choice_tags = choice_tags # triggers property
        self.max_selection_size = max_selection_size # triggers property


    def __deepcopy__(self, memo):
        result = super(Select2TagsField, self).__deepcopy__(memo)
        result._choice_tags = copy.deepcopy(self._choice_tags, memo) # in case it's modified in place by end user
        return result


    '''
    def coerce_value(self, value):
        """
        Coerces ``value`` to a Python data type.
        Sub-classes should override this if they do not want unicode values.
        """
        return super(Select2TagsField, self).coerce_value(value=value)
    '''

    def validate(self, value):
        """
        Validates that the input is in self.choices.
        """
        super(Select2TagsField, self).validate(value)
        if value and self.max_selection_size > 0:
            if len(value) > self.max_selection_size:
                raise ValidationError(self.error_messages['too_many'])


    def _get_choice_tags(self):
        return self._choice_tags

    def _set_choice_tags(self, value):
        # tags can be any iterable, but we call list() on it because
        # it will be consumed more than once.
        self._choice_tags = list(value)
        self.widget.set_choice_tags(self._choice_tags)

    choice_tags = property(_get_choice_tags, _set_choice_tags)


    def _get_max_selection_size(self):
        return self._max_selection_size

    def _set_max_selection_size(self, value):
        self._max_selection_size = value
        self.widget.set_max_selection_size(self._max_selection_size)

    max_selection_size = property(_get_max_selection_size, _set_max_selection_size)


'''
class MultipleTagField(forms.Field):

    def prepare_value(self, value):
        return value

    def to_python(self, value):
        return value
        
        
        
            def ___clean(self):
        cleaned_data = super(StaticPageForm, self).clean()

        cleaned_data["categories"] = cleaned_data["categories"].split(SEPARATOR)
        cleaned_data["keywords"] = cleaned_data["keywords"].split(SEPARATOR)

        # Always return the full collection of cleaned data.
        return cleaned_data

'''
