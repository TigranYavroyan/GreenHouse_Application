import { Sequelize } from "sequelize";

export default class ConfigPostgres {
    static ensureInstance() {
        if (!ConfigPostgres.instance) {
            ConfigPostgres.instance = new Sequelize(
                process.env.POSTGRES_DB,
                process.env.POSTGRES_USER,
                process.env.POSTGRES_PASSWORD,
                {
                    host: process.env.POSTGRES_HOST,
                    port: process.env.POSTGRES_PORT,
                    dialect: 'postgres',
                    logging: false,
                }
            );
        }

        return ConfigPostgres.instance;
    }

    static async init() {
        const sequelize = ConfigPostgres.ensureInstance();

        try {
            await sequelize.authenticate();
            console.log('✅ Database connection established.');

            // ⚠️ Dev only options
            await sequelize.sync({
                alter: true,   // updates tables without dropping
                // force: true, // drops & recreates tables (DANGEROUS)
            });

            console.log('✅ Models synchronized.');
        } catch (error) {
            console.error('❌ Database initialization failed:', error);
            process.exit(1);
        }

        return sequelize;
    }

    static async getInstance() {
        return ConfigPostgres.ensureInstance();
    }
}