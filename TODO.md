# TODO - documented gaps against the customer-facing API at the pin

Per the series rule: a required property/BIBB the public API cannot express is named
here, not faked. Re-verify both entries whenever the series pin moves.

## Calendar 1 ("Cream") Date_List - no customer-surface callback shape

`Date_List` (cl. 12.8) is a `BACnetLIST of BACnetCalendarEntry`: a variable-length list
of a CHOICE (Date | DateRange | WeekNDay). Verified against
`submodules/cas-bacnet-stack/source/CASBACnetStackDLL.h` at pin `abd4cee1c7f28ca8e1af4720849c4081082bbe82`
(`grep -n "DllExport.*RegisterCallbackGetProperty" source/CASBACnetStackDLL.h`): none of
the typed `RegisterCallbackGetProperty*` exports accept a list-of-CHOICE shape, so this
example cannot serve `Date_List` and leaves it to the stack default (an empty/unknown-property
read). `Present_Value` (`"is today in Date_List"`) is therefore honestly served as always
`false` - see `docs/objects.json`'s Calendar entry.

This does **not** block SCHED-E-B: Schedule 1's own demo exception event uses
`BACnetStack_AddScheduleExceptionEventWithCalendarEntry` (the direct date/period form),
which the stack's own doc comment confirms is fully functional and independent of this gap.

## `BACnetStack_AddScheduleExceptionEventWithCalendarReference` does not resolve Date_List

Also verified at the same pin, `CASBACnetStackDLL.h`'s doc comment for that export (the
form that references a *Calendar object* rather than a literal date/period) states
explicitly: "does NOT yet resolve that object's Date_List at evaluation time... stored
but never currently matches. See issue #963." This example therefore does not use that
export; it uses `AddScheduleExceptionEventWithCalendarEntry` instead (see above), and
Calendar 1 exists as a real, independently-readable object rather than as the
Schedule's exception-event source.

Filed upstream: [chipkin/cas-bacnet-stack#2034](https://github.com/chipkin/cas-bacnet-stack/issues/2034)
(the missing customer-surface callback shape for Date_List itself - distinct from #963,
which is about the Calendar-reference form of a Schedule exception event specifically).
