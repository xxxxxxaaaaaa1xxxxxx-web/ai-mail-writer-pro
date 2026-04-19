import { logger } from '../services/logger.js';

/**
 * Base class for all AI employees. Each employee implements `run` which takes
 * a typed input and returns a typed output. The base class handles logging and
 * a simple retry policy.
 */
export abstract class AiEmployee<TInput, TOutput> {
  abstract readonly name: string;
  abstract readonly role: string;

  /** Max attempts before escalating to Hades. */
  protected readonly maxAttempts = 3;

  abstract execute(input: TInput): Promise<TOutput>;

  async run(input: TInput): Promise<TOutput> {
    let lastError: unknown;
    for (let attempt = 1; attempt <= this.maxAttempts; attempt++) {
      try {
        logger.info(
          { employee: this.name, attempt },
          `${this.name} starting`,
        );
        const output = await this.execute(input);
        logger.info({ employee: this.name }, `${this.name} completed`);
        return output;
      } catch (err) {
        lastError = err;
        const msg = err instanceof Error ? err.message : String(err);
        logger.warn(
          { employee: this.name, attempt, error: msg },
          `${this.name} attempt failed`,
        );
        if (attempt < this.maxAttempts) {
          const backoffMs = 2000 * attempt;
          await new Promise((r) => setTimeout(r, backoffMs));
        }
      }
    }
    throw new Error(
      `${this.name} failed after ${this.maxAttempts} attempts: ${
        lastError instanceof Error ? lastError.message : String(lastError)
      }`,
    );
  }
}
