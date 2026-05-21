const m = require('zigbee-herdsman-converters/lib/modernExtend');

module.exports = {
    zigbeeModel: ['TLSR82xx'],
    model: 'TLSR82xx',
    vendor: 'Aubor',
    description: 'Roller shade',
    extend: [
        m.windowCovering({controls: ['lift']}),
        m.battery(),
    ],
};
