import { promises as fs } from 'node:fs';
import path from 'node:path';
import { config } from '../config.js';

/**
 * Simple file-based storage for the MVP. Writes each artifact to
 * {OUTPUT_DIR}/{week}/{topicId}/{kind}.{ext}. Swap in Prisma/S3 later by
 * changing just this file.
 */
export class Storage {
  private readonly root: string;

  constructor(root: string = config.output.dir) {
    this.root = root;
  }

  private async ensureDir(topicId: string, week: string): Promise<string> {
    const dir = path.join(this.root, week, topicId);
    await fs.mkdir(dir, { recursive: true });
    return dir;
  }

  async saveJson(
    week: string,
    topicId: string,
    kind: string,
    data: unknown,
  ): Promise<string> {
    const dir = await this.ensureDir(topicId, week);
    const file = path.join(dir, `${kind}.json`);
    await fs.writeFile(file, JSON.stringify(data, null, 2), 'utf8');
    return file;
  }

  async saveText(
    week: string,
    topicId: string,
    filename: string,
    content: string,
  ): Promise<string> {
    const dir = await this.ensureDir(topicId, week);
    const file = path.join(dir, filename);
    await fs.writeFile(file, content, 'utf8');
    return file;
  }

  async loadJson<T>(week: string, topicId: string, kind: string): Promise<T> {
    const file = path.join(this.root, week, topicId, `${kind}.json`);
    const data = await fs.readFile(file, 'utf8');
    return JSON.parse(data) as T;
  }
}
