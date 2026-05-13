import {
  IsBoolean,
  IsOptional,
  IsString,
} from 'class-validator';

export class CreateMarketplaceDto {
  @IsString()
  name: string;

  @IsString()
  baseUrl: string;

  @IsOptional()
  @IsString()
  logoUrl?: string;

  @IsOptional()
  @IsBoolean()
  active?: boolean;
}