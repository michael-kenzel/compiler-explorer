// Copyright (c) 2012, Matt Godbolt
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//     * Redistributions of source code must retain the above copyright notice,
//       this list of conditions and the following disclaimer.
//     * Redistributions in binary form must reproduce the above copyright
//       notice, this list of conditions and the following disclaimer in the
//       documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.

const fs = require('fs'),
    logger = require('./logger').logger,
    _ = require('underscore'),
    path = require('path');

let properties = {};

let propDebug = false;

function debug(string) {
    if (propDebug) logger.info(`prop: ${string}`);
}


class PropertiesLayer {
    constructor(name, parent = default_properties_layer) {
        this.name = name;
        this.properties = new Map();
        this.parent = parent;
    }

    add(property, value) {
        this.properties[property] = value;
    }

    has(property) {
        return this.properties.has(property) || this.parent.has(property);
    }

    get(key, property, defaultValue) {
        const value = this.properties.get(property);
        if (value === undefined) {
            return this.parent.get(key, property, defaultValue);
        }
        else if (this.parent.has(property)) {
            debug(`${key}.${property}: ${this.name} overriding parent value (${this.parent.get(key, property, defaultValue)}) with ${value}`);
        }
        debug(`${base}.${property}: returning ${result} (from ${this.name})`);
        return value;
    }
}

class DefaultPropertiesLayer {
    constructor() {
        this.name = "<default>";
        this.parent = this;
    }

    has(_key) {
        return false;
    }

    get(_key, _property, defaultValue) {
        return defaultValue;
    }
}

let default_properties_layer = new DefaultPropertiesLayer();

function get(base, property, defaultValue) {
    const map = properties[base];
    if (map) {
        return map.get(base, property, defaultValue);
    }
    debug(`${base}.${property}: no config found, returning default value`);
    return defaultValue;
}

function toProperty(prop) {
    if (prop === 'true' || prop === 'yes') return true;
    if (prop === 'false' || prop === 'no') return false;
    if (prop.match(/^-?(0|[1-9][0-9]*)$/)) return parseInt(prop);
    if (prop.match(/^-?[0-9]*\.[0-9]+$/)) return parseFloat(prop);
    return prop;
}

function parseProperties(builder, blob, name) {
    blob.split('\n').forEach((line, index) => {
        line = line.replace(/#.*/, '').trim();
        if (!line) return;
        let split = line.match(/([^=]+)=(.*)/);
        if (!split) {
            logger.error(`Bad line: ${line} in ${name}: ${index + 1}`);
            return;
        }
        const key = split[1].trim();
        const val = split[2].trim();
        debug(`${key} = ${val}`);
        builder.add(key, toProperty(val));
    });
}

function matchLayerName(layer, hierarchy) {
    // layer name syntax: <key>.<source>[.<fragment>]
    // example: c++.local.msvc
    // try to match valid .<source>[.<fragment>] at end of layer name
    const sourcePartStart = layer.indexOf('.');
    if (sourcePartStart >= 0) {
        const sourcePart = layer.slice(sourcePartStart + 1);
        for (let i = 0; i < hierarchy.length; ++i) {
            const source = hierarchy[i];
            if (sourcePart.startsWith(source)) {
                const fragment = sourcePart.slice(source.length);
                if (!fragment || fragment[0] == '.') {
                    return [layer.slice(0, sourcePartStart), source, i, fragment.slice(1)];
                }
            }
        }
    }
    return undefined;
}

function buildConfig(builder, hierarchy, directory, baseLayerName = "") {
    for (let filename of fs.readdirSync(directory)) {
        const fullpath = path.join(directory, filename);
        if (filename.endsWith(".properties")) {
            const layername = baseLayerName + filename.slice(0, -11);
            const match = matchLayerName(layername, hierarchy);
            if (match) {
                const [key, source, ordinal, fragment] = match;
                builder.addLayer(key, source, ordinal, fragment, fullpath);
            }
        }
        else if (fs.statSync(fullpath).isDirectory()) {
            buildConfig(builder, hierarchy, fullpath, filename + '.');
        }
    }
}

class ConfigBuilder {
    constructor() {
        this.properties = new Map();
    }

    createLayer(key, source, ordinal, fragment, parent, path) {
        let layer = new PropertiesLayer(`${key}.${source}`, parent);
        layer.ordinal = ordinal;
        layer.fragments = new Set([fragment]);
        parseProperties(layer, fs.readFileSync(path, 'utf-8'), path);
        return layer;
    }

    mergeLayer(layer, fragment, path) {
        if (layer.fragments.has(fragment)) {
            logger.warn(`${path} adds already existing fragment ${fragment}`);
        }
        parseProperties({
            add: function(property, value) {
                if (layer.has(property)) {
                    logger.warn(`${path} overwrites existing ${layer.name}.${property}`);
                }
                layer.add(property, value);
            }
        }, fs.readFileSync(path, 'utf-8'), path);
        layer.fragments.add(fragment);
        return layer;
    }

    addLayer(key, source, ordinal, fragment, path) {
        debug('Adding config from ' + path);

        let begin = this.properties[key] || default_properties_layer;

        let insertBefore = l => (l == l.parent || l.ordinal < ordinal);

        if (insertBefore(begin)) {
            const layer = this.createLayer(key, source, ordinal, fragment, begin, path);
            this.properties[key] = layer;
            return layer;
        }

        for (let l = begin; ; l = l.parent) {
            if (insertBefore(l.parent)) {
                if (l.ordinal == ordinal) {
                    return this.mergeLayer(l, fragment, path);
                }
                const layer = this.createLayer(key, source, ordinal, fragment, l.parent, path);
                l.parent = layer;
                return layer;
            }
        }
    }
}

function initialize(directory, hier) {
    if (hier === null) throw new Error('Must supply a hierarchy array');
    const hierarchy = _.map(hier, x => x.toLowerCase());
    logger.info(`Reading properties from ${directory} with hierarchy ${hierarchy}`);
    let builder = new ConfigBuilder();
    buildConfig(builder, hierarchy, directory);
    properties = builder.properties;
    logger.debug("props.properties = ", properties);
}

function propsFor(base) {
    return function (property, defaultValue) {
        return get(base, property, defaultValue);
    };
}

// function mappedOf(fn, funcA, funcB) {
//     const resultA = funcA();
//     if (resultA !== undefined) return resultA;
//     return funcB();
// }

/***
 * Compiler property fetcher
 */
class CompilerProps {
    /***
     * Creates a CompilerProps lookup function
     *
     * @param {CELanguages} languages - Supported languages
     * @param {function} ceProps - propsFor function to get Compiler Explorer values from
     */
    constructor(languages, ceProps) {
        this.languages = languages;
        this.propsByLangId = {};

        this.ceProps = ceProps;

        // Instantiate a function to access records concerning the chosen language in hidden object props.properties
        _.each(this.languages, lang => this.propsByLangId[lang.id] = propsFor(lang.id));
    }

    $getInternal(langId, key, defaultValue) {
        const languagePropertyValue = this.propsByLangId[langId](key);
        if (languagePropertyValue !== undefined) {
            return languagePropertyValue;
        }
        return this.ceProps(key, defaultValue);
    }

    /***
     * Gets a value for a given key associated to the given languages from the properties
     *
     * @param {?(string|CELanguages)} langs - Which langs to search in
     *  For compatibility, {null} means looking into the Compiler Explorer properties (Not on any language)
     *  If langs is a {string}, it refers to the language id we want to search into
     *  If langs is a {CELanguages}, it refers to which languages we want to search into
     *  TODO: Add a {Language} version?
     * @param {string} key - Key to look for
     * @param {*} defaultValue - What to return if the key is not found
     * @param {?function} fn - Transformation to give to each value found
     * @returns {*} Transformed value(s) found or fn(defaultValue)
     */
    get(langs, key, defaultValue, fn = _.identity) {
        fn = fn || _.identity;
        if (_.isEmpty(langs)) {
            return fn(this.ceProps(key, defaultValue));
        }
        if (!_.isString(langs)) {
            return _.chain(langs)
                .map(lang => [lang.id, fn(this.$getInternal(lang.id, key, defaultValue), lang)])
                .object()
                .value();
        } else {
            if (this.propsByLangId[langs]) {
                return fn(this.$getInternal(langs, key, defaultValue), this.languages[langs]);
            } else {
                logger.error(`Tried to pass ${langs} as a language ID`);
                return fn(defaultValue);
            }
        }
    }
}

module.exports = {
    get: get,
    propsFor: propsFor,
    initialize: initialize,
    CompilerProps: CompilerProps,
    setDebug: debug => {
        propDebug = debug;
    },
    fakeProps: fake => (prop, def) => fake[prop] === undefined ? def : fake[prop]
};
