/* place-search.js
 *
 * Adds Geoapify autocomplete (suggestions while typing) to a text input.
 *
 * How the whole search chain works:
 *   1. While typing, this file shows Geoapify suggestions, Malta only.
 *   2. The user picks one: onSelect gets { label, lat, lon }. No more calls.
 *   3. No good suggestion, or Geoapify fails: the user types the full name and
 *      presses Enter. This file calls onEnter(text). THE PAGE decides what
 *      happens then: later it will ask the backend (OpenStreetMap search).
 *   4. If the backend also fails, the page shows the list of 50 places.
 *      This file does not do steps 3 and 4. See the two marked spots in ride-page.js.
 *
 * The backend must still check every point against the Malta bounds.
 * Coordinates sent by the browser are never trusted.
 *
 * Needs AUTH_CONFIG.geoapifyKey from auth-config.js. While the key is still
 * the placeholder, autocomplete is skipped quietly and Enter still works.
 */
(function () {
    "use strict";

    var ENDPOINT = "https://api.geoapify.com/v1/geocode/autocomplete";
    var MIN_CHARS = 2; // start asking after this many letters
    var WAIT_MS = 300; // wait for a pause in typing
    var MAX_RESULTS = 5;
    var PAUSE_AFTER_FAILURE_MS = 5 * 60 * 1000; // stop asking for a while after an error

    var pausedUntil = 0; // shared by every input on the page
    var counter = 0;

    function getKey() {
        if (typeof AUTH_CONFIG === "undefined") {
            return "";
        }
        var key = AUTH_CONFIG.geoapifyKey;
        if (!key || key.indexOf("PASTE_") === 0) {
            return "";
        }
        return key;
    }

    async function fetchSuggestions(text, signal) {
        var params = new URLSearchParams({
            text: text,
            filter: "countrycode:mt",
            limit: String(MAX_RESULTS),
            lang: "en",
            format: "json",
            apiKey: getKey(),
        });
        var response = await fetch(ENDPOINT + "?" + params.toString(), { signal: signal });
        if (!response.ok) {
            throw new Error("status " + response.status);
        }
        var data = await response.json();
        var rows = Array.isArray(data.results) ? data.results : [];
        return rows
            .filter(function (row) {
                return Number.isFinite(row.lat) && Number.isFinite(row.lon) && row.formatted;
            })
            .map(function (row) {
                return { label: String(row.formatted), lat: row.lat, lon: row.lon };
            });
    }

    /**
     * attach(input, options)
     *   options.onSelect(place)  the user picked a suggestion: { label, lat, lon }
     *   options.onClear()        the user changed the text after picking, so the
     *                            saved place no longer matches the box
     *   options.onEnter(text)    the user pressed Enter with typed text and no pick
     *   options.onUnavailable()  Geoapify failed (optional)
     * Returns { getSelected(), clear(), enabled }.
     */
    function attach(input, options) {
        options = options || {};
        var autocompleteOn = getKey() !== "";
        var selected = null;
        var items = [];
        var activeIndex = -1;
        var timer = null;
        var controller = null;
        var listId = "place-search-list-" + ++counter;

        var list = document.createElement("ul");
        list.className = "place-search-list";
        list.id = listId;
        list.setAttribute("role", "listbox");
        list.hidden = true;

        input.parentElement.classList.add("place-search");
        input.parentElement.appendChild(list);
        input.setAttribute("autocomplete", "off");
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-controls", listId);
        input.setAttribute("aria-expanded", "false");

        function closeList() {
            items = [];
            activeIndex = -1;
            list.hidden = true;
            while (list.firstChild) {
                list.removeChild(list.firstChild);
            }
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
        }

        function highlight(index) {
            activeIndex = index;
            Array.prototype.forEach.call(list.children, function (li, i) {
                li.classList.toggle("is-active", i === index);
            });
            if (index >= 0) {
                input.setAttribute("aria-activedescendant", listId + "-" + index);
            } else {
                input.removeAttribute("aria-activedescendant");
            }
        }

        function choose(item) {
            selected = item;
            input.value = item.label;
            closeList();
            if (options.onSelect) {
                options.onSelect({ label: item.label, lat: item.lat, lon: item.lon });
            }
        }

        function render(found) {
            closeList();
            if (found.length === 0) {
                return;
            }
            items = found;
            found.forEach(function (item, i) {
                var li = document.createElement("li");
                li.id = listId + "-" + i;
                li.setAttribute("role", "option");
                li.textContent = item.label; // text only, never HTML
                // mousedown, not click, so the input does not lose focus first
                li.addEventListener("mousedown", function (event) {
                    event.preventDefault();
                    choose(item);
                });
                list.appendChild(li);
            });
            list.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        async function run(text) {
            if (controller) {
                controller.abort(); // a newer search replaces the old one
            }
            controller = new AbortController();
            try {
                var found = await fetchSuggestions(text, controller.signal);
                if (input.value.trim() !== text) {
                    return; // the text changed while waiting
                }
                render(found);
            } catch (error) {
                if (error && error.name === "AbortError") {
                    return;
                }
                pausedUntil = Date.now() + PAUSE_AFTER_FAILURE_MS;
                closeList();
                if (options.onUnavailable) {
                    options.onUnavailable();
                }
            }
        }

        input.addEventListener("input", function () {
            if (selected) {
                selected = null;
                if (options.onClear) {
                    options.onClear();
                }
            }
            clearTimeout(timer);
            if (!autocompleteOn || Date.now() < pausedUntil) {
                closeList();
                return;
            }
            var text = input.value.trim();
            if (text.length < MIN_CHARS) {
                if (controller) {
                    controller.abort();
                }
                closeList();
                return;
            }
            timer = setTimeout(function () {
                run(text);
            }, WAIT_MS);
        });

        input.addEventListener("keydown", function (event) {
            var open = !list.hidden && items.length > 0;
            if (event.key === "ArrowDown" && open) {
                event.preventDefault();
                highlight((activeIndex + 1) % items.length);
            } else if (event.key === "ArrowUp" && open) {
                event.preventDefault();
                highlight(activeIndex <= 0 ? items.length - 1 : activeIndex - 1);
            } else if (event.key === "Escape" && open) {
                closeList();
            } else if (event.key === "Enter") {
                if (open && activeIndex >= 0) {
                    event.preventDefault();
                    choose(items[activeIndex]);
                } else if (!selected && input.value.trim() !== "") {
                    event.preventDefault();
                    clearTimeout(timer);
                    if (controller) {
                        controller.abort();
                    }
                    closeList();
                    if (options.onEnter) {
                        options.onEnter(input.value.trim());
                    }
                }
            }
        });

        input.addEventListener("blur", closeList);

        return {
            enabled: autocompleteOn,
            getSelected: function () {
                return selected ? { label: selected.label, lat: selected.lat, lon: selected.lon } : null;
            },
            clear: function () {
                selected = null;
                input.value = "";
                closeList();
            },
        };
    }

    window.PlaceSearch = { attach: attach };
})();